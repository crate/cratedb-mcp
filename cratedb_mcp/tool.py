import contextlib
import contextvars
import logging
import time
import typing as t

import httpx
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field
from sqlparse.exceptions import SQLParseError

from cratedb_mcp.knowledge import DocumentationIndex, Queries
from cratedb_mcp.settings import Settings
from cratedb_mcp.util.sql import sql_is_permitted

logger = logging.getLogger(__name__)

calling_tool: contextvars.ContextVar[str] = contextvars.ContextVar("calling_tool", default="-")


class CrateError(ToolError):
    """An error CrateDB answered to a statement."""


class StatementTimeout(ToolError):
    """CrateDB did not answer a statement within the HTTP timeout."""


def shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "…"


def _is_none(value: t.Any) -> bool:
    return value is None


def absent() -> t.Any:
    return Field(default=None, exclude_if=_is_none)


def declare_present_types(schema: t.Dict[str, t.Any]) -> None:
    """Declare only the types a field holds when present: absent fields are left out, never null."""
    schema.pop("additionalProperties", None)
    for prop in schema["properties"].values():
        prop.pop("default", None)
        if "anyOf" in prop:
            (kept,) = [option for option in prop.pop("anyOf") if option != {"type": "null"}]
            prop.update(kept)


class CrateResult(BaseModel):
    model_config = ConfigDict(extra="allow", json_schema_extra=declare_present_types)

    cols: t.Optional[t.List[str]] = absent()
    rows: t.Optional[t.List[t.List[t.Any]]] = absent()
    rowcount: t.Optional[int] = absent()
    duration: t.Optional[float] = absent()


# ------------------------------------------
#              Text-to-SQL
# ------------------------------------------
def query_cratedb(query: str) -> dict:
    """Send the SQL `query` to the configured CrateDB server and return its answer."""
    started = time.monotonic()
    answer = None
    try:
        answer = read_answer(query)
        return answer
    finally:
        took = (time.monotonic() - started) * 1000
        if answer is None or "error" in answer:
            logger.info("%s: CrateDB call failed after %d ms", calling_tool.get(), took)
        else:
            rows = len(answer.get("rows", ()))
            logger.info("%s: CrateDB call took %d ms, %d rows", calling_tool.get(), took, rows)


def sql_endpoint() -> t.Tuple[httpx.URL, t.Optional[t.Tuple[str, str]]]:
    """Return the URL of CrateDB's SQL endpoint without the user part, and the credentials."""
    cluster = Settings.cluster_url()
    path = cluster.path.rstrip("/") + "/_sql"
    url = cluster.copy_with(userinfo=b"", path=path)
    return url, (cluster.username, cluster.password) if cluster.userinfo else None


def read_answer(query: str) -> dict:
    """Send the SQL `query` to the configured CrateDB server and read its answer."""
    url, auth = sql_endpoint()
    response = httpx.post(url, json={"stmt": query}, auth=auth, timeout=Settings.http_timeout())
    try:
        return response.json()
    except ValueError as e:
        text = shorten(response.text.strip(), 200)
        raise ToolError(
            f"CrateDB answered HTTP {response.status_code}" + (f": {text}" if text else ".")
        ) from e


def query_result(query: str) -> dict:
    """Run `query` and return its result, raising CrateDB's error."""
    try:
        result = query_cratedb(query)
    except httpx.TimeoutException as e:
        raise StatementTimeout(
            f"CrateDB did not answer within the {Settings.http_timeout():g}-second timeout."
        ) from e
    if "error" in result:
        raise CrateError(f"{result['error']['message']} (error code {result['error']['code']})")
    return result


def run_query(query: str) -> dict:
    """Run a query written by the model, and advise narrowing one that is too slow."""
    try:
        return query_result(query)
    except StatementTimeout as e:
        raise ToolError(
            f"The query did not finish within the {Settings.http_timeout():g}-second timeout. "
            "Narrow it with a WHERE clause, an aggregation or a LIMIT instead of running it again."
        ) from e


@contextlib.contextmanager
def read_only_check() -> t.Iterator[None]:
    """Fail the call when the read-only check cannot analyze a statement."""
    try:
        yield
    except SQLParseError as e:
        raise ToolError(
            f"The read-only check cannot analyze this statement: {str(e).rstrip('.')}. "
            "Shorten it, or split it into smaller queries."
        ) from e


def query_sql(query: str) -> CrateResult:
    """
    Execute an SQL query on CrateDB and return the results.
    Select only the columns you need (avoid `SELECT *`) and,
    where appropriate, add a `LIMIT` clause to keep result sets concise.
    """
    with read_only_check():
        permitted = sql_is_permitted(query)
    if not permitted:
        raise ToolError("Only queries that have a SELECT statement are allowed.")
    return CrateResult(**run_query(query))


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

    response = {}
    for variant, where in variants.items():
        query = Queries.TABLES_COLUMNS.format(where=where)
        response[variant] = query_result(query)
    return response


def get_table_metadata() -> dict:
    """
    Return table metadata for all tables stored in CrateDB.
    Return an aggregation of schema:tables, e.g.: {'doc': [{name:'mytable', ...}, ...]}

    The tables have metadata datapoints like replicas, shards,
    name, version, total_shards, total_records.
    """
    return query_result(Queries.TABLES_METADATA)


# ------------------------------------------
#          Documentation inquiry
# ------------------------------------------

# Load CrateDB documentation outline.
documentation_index = DocumentationIndex()


class DocumentationLink(BaseModel):
    title: str
    link: str
    description: str
    markdown_enabled: bool


def get_cratedb_documentation_index() -> t.List[DocumentationLink]:
    """
    Return the table of contents for the curated CrateDB documentation index.
    Use it whenever you need to verify CrateDB-specific details or syntax.
    """
    return [DocumentationLink(**item) for item in documentation_index.items()]


def fetch_cratedb_docs(link: str) -> str:
    """
    Given a `link` returned by `get_cratedb_documentation_index`,
    fetch the full content of that documentation page. Content
    can be quoted verbatim when answering questions about CrateDB.
    """
    return documentation_index.fetch(link)


# ------------------------------------------
#            Health / Status
# ------------------------------------------
def get_cluster_health() -> CrateResult:
    """Return the health of each table and partition from `sys.health`, most severe first."""
    return CrateResult(**query_result(Queries.HEALTH))
