import json
import os
import sqlite3
import threading
import typing as t

import httpx
from fastmcp.exceptions import ToolError

from cratedb_mcp.knowledge import DocumentationIndex, Queries
from cratedb_mcp.settings import Settings
from cratedb_mcp.util.sql import sql_denial_message, sql_is_permitted


class ResultTooLarge(ToolError):
    """
    A tool result exceeds the configured maximum size.
    """


# ------------------------------------------
#              HTTP plumbing
# ------------------------------------------
def _http_client() -> httpx.Client:
    """
    Build an HTTP client for the CrateDB cluster.

    Credentials are applied out of band, they never become part of the URL.
    """
    headers = {}
    token = Settings.cluster_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(
        base_url=Settings.cluster_url(),
        auth=None if token else Settings.cluster_auth(),
        headers=headers,
        timeout=Settings.http_timeout(),
    )


# Environment variables the HTTP client for the CrateDB cluster is derived from.
_client_variables = (
    "CRATEDB_CLUSTER_URL",
    "CRATEDB_USERNAME",
    "CRATEDB_PASSWORD",
    "CRATEDB_TOKEN",
    "CRATEDB_MCP_HTTP_TIMEOUT",
)
_client_lock = threading.Lock()
_client_cache: t.Dict[t.Tuple[t.Optional[str], ...], httpx.Client] = {}


def _shared_client() -> httpx.Client:
    """
    Return an HTTP client shared across tool invocations, to reuse connections.

    Tools run in a thread pool, `httpx.Client` is safe to share between threads.
    The client is rebuilt when its settings change, because they are read at runtime.
    """
    key = tuple(os.getenv(name) for name in _client_variables)
    with _client_lock:
        client = _client_cache.get(key)
        if client is None or client.is_closed:
            # Settings do not change while serving requests, so superseded clients are idle.
            for superseded in _client_cache.values():
                superseded.close()
            _client_cache.clear()
            client = _client_cache[key] = _http_client()
        return client


def _read_limited(response: httpx.Response, hint: str) -> bytes:
    """
    Read the body of a streamed response, giving up beyond the configured maximum size.

    Reading incrementally keeps oversized results from being loaded into memory.
    The limit applies to the decoded body, so it also covers compressed responses.
    """
    limit = Settings.result_max_bytes()
    body = bytearray()
    for chunk in response.iter_bytes():
        body.extend(chunk)
        if len(body) > limit:
            raise ResultTooLarge(f"Result exceeds the configured maximum of {limit} bytes. {hint}")
    return bytes(body)


def _request_cratedb(client: httpx.Client, method: str, path: str, **kwargs: t.Any) -> dict:
    """
    Submit a request to CrateDB, and return its JSON payload, guarded by the result size limit.
    """
    with client.stream(method, path, **kwargs) as response:
        body = _read_limited(
            response,
            hint="Please refine your request, e.g. by selecting fewer columns, "
            "adding a LIMIT clause, or using aggregations.",
        )
    return _response_payload(response, body)


def _response_payload(response: httpx.Response, body: bytes) -> dict:
    """
    Return the JSON payload of a CrateDB response.

    CrateDB reports statement errors as an `error` object, usually along with
    an HTTP error status code. Those are turned into tool execution errors, so
    the LLM can correct its query, and server-internal details stay behind.
    """
    try:
        payload = json.loads(body)
    except ValueError as e:
        excerpt = body[:200].decode("utf-8", errors="replace")
        raise ToolError(
            f"CrateDB responded with HTTP {response.status_code} and a non-JSON body: {excerpt!r}"
        ) from e

    # Intermediaries like proxies may respond with arbitrary JSON documents.
    if not isinstance(payload, dict):
        raise ToolError(
            f"CrateDB responded with HTTP {response.status_code} "
            f"and an unexpected JSON payload of type `{type(payload).__name__}`"
        )

    error = payload.get("error")
    if isinstance(error, dict):
        raise ToolError(f"CrateDB error {error.get('code')}: {error.get('message')}")
    if error:
        raise ToolError(f"CrateDB error: {error}")

    response.raise_for_status()
    payload.pop("error_trace", None)
    return payload


def _result_size(payload: t.Any) -> int:
    """
    Return the size of a tool result in bytes, when serialized to JSON.
    """
    return len(json.dumps(payload, default=str, ensure_ascii=False).encode("utf-8"))


# ------------------------------------------
#              Text-to-SQL
# ------------------------------------------
def query_cratedb(query: str) -> dict:
    """Send the SQL `query` to the configured CrateDB server and return the result."""
    return _request_cratedb(_shared_client(), "POST", "/_sql", json={"stmt": query})


def query_sql(query: str) -> dict:
    """
    Execute an SQL query on CrateDB and return the results.
    Select only the columns you need (avoid `SELECT *`) and,
    where appropriate, add a `LIMIT` clause to keep result sets concise.
    """
    if not sql_is_permitted(query):
        raise PermissionError(sql_denial_message(query))
    return query_cratedb(query)


def get_table_columns() -> dict:
    """
    Return schema and column information for all tables stored in CrateDB from
    its `information_schema` table. Use it to discover database entities you are
    unfamiliar with, the column names are crucial for correctly formulating SQL
    queries.

    The returned fields are table_schema, table_name, column_name,
    data_type, is_nullable, and column_default.

    The returned sections are:
    - user tables: includes all user-defined tables without system tables
    - system tables: `information_schema`, `pg_catalog`, and `sys`.

    Sections which exceed the result size limit are omitted, with a hint
    how to inquire the same information selectively using `query_sql`.
    """

    variants = {
        "user": """
            table_schema != 'information_schema' AND
            table_schema != 'pg_catalog' AND
            table_schema != 'sys'
        """,
        "information_schema": "table_schema = 'information_schema'",
        "pg_catalog": "table_schema = 'pg_catalog'",
        "sys": "table_schema = 'sys'",
    }

    # The tool accepts no parameters, so the LLM can not refine its request.
    # Instead of failing altogether on large schemas, omit oversized sections.
    remaining = Settings.result_max_bytes()
    response: t.Dict[str, t.Any] = {}
    for variant, where in variants.items():
        query = Queries.TABLES_COLUMNS.format(where=where)
        try:
            section = query_sql(query)
            size = _result_size(section)
        except ResultTooLarge:
            size = remaining + 1
        if size > remaining:
            response[variant] = {
                "omitted": "This section exceeds the result size limit. Please use `query_sql` on "
                f"`information_schema.columns`, using the filter `{' '.join(where.split())}`, "
                "narrowed down by `table_schema` or `table_name`."
            }
            continue
        remaining -= size
        response[variant] = section
    return response


def get_table_metadata() -> dict:
    """
    Return table metadata for all tables stored in CrateDB.
    Return an aggregation of schema:tables, e.g.: {'doc': [{name:'mytable', ...}, ...]}

    The tables have metadata datapoints like replicas, shards,
    name, version, total_shards, total_records.
    """
    return query_cratedb(Queries.TABLES_METADATA)


def get_cluster_version(timeout: t.Optional[float] = None) -> str:
    """
    Return the version of the configured CrateDB cluster.
    """
    kwargs = {} if timeout is None else {"timeout": timeout}
    version = _request_cratedb(_shared_client(), "GET", "/", **kwargs).get("version")
    return version.get("number", "unknown") if isinstance(version, dict) else "unknown"


# ------------------------------------------
#          Documentation inquiry
# ------------------------------------------

# Load CrateDB documentation outline.
documentation_index = DocumentationIndex()


def get_cratedb_documentation_index() -> list:
    """
    Return the table of contents for the curated CrateDB documentation index.
    Use it whenever you need to verify CrateDB-specific details or syntax.
    """
    return documentation_index.items()


def fetch_cratedb_docs(link: str) -> str:
    """
    Given a `link` returned by `get_cratedb_documentation_index`,
    fetch the full content of that documentation page. Content
    can be quoted verbatim when answering questions about CrateDB.
    """
    if not documentation_index.url_permitted(link):
        raise ValueError(f"Link is not permitted: {link}")
    try:
        return _fetch_document(documentation_index.client, link)
    except sqlite3.Error as e:
        # The cache is shared between server processes, and may fail at any time,
        # e.g. when it is locked, or became read-only. Carry on without it.
        documentation_index.disable_cache(reason=e)
        return _fetch_document(documentation_index.client, link)


def _fetch_document(client: httpx.Client, link: str) -> str:
    """
    Fetch a documentation page, guarded by the result size limit.
    """
    with client.stream("GET", link, timeout=Settings.http_timeout()) as response:
        response.raise_for_status()
        body = _read_limited(
            response, hint="Please open the documentation page in a browser instead."
        )
        # NB: httpx falls back to UTF-8 when the announced character set is unknown.
        encoding = response.encoding or "utf-8"
    return body.decode(encoding, errors="replace")


# ------------------------------------------
#            Health / Status
# ------------------------------------------
def get_cluster_health() -> dict:
    """Return the health of the CrateDB cluster by querying `sys.health` ordered by severity."""
    return query_cratedb(Queries.HEALTH)
