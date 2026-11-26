import contextlib
import json
import typing as t

import httpx
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlparse.exceptions import SQLParseError

from cratedb_mcp.knowledge import DocumentationIndex, Queries
from cratedb_mcp.settings import HTTP_URL, Settings
from cratedb_mcp.util.sql import sql_is_permitted


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


class BoundedResult(CrateResult):
    truncated: t.Optional[bool] = absent()
    rows_returned: t.Optional[int] = absent()
    note: t.Optional[str] = absent()

    @model_validator(mode="after")
    def count_rows(self) -> "BoundedResult":
        self.rows_returned = None if self.rows is None else len(self.rows)
        return self


# ------------------------------------------
#              Text-to-SQL
# ------------------------------------------
def query_cratedb(query: str) -> dict:
    """Send the SQL `query` to the configured CrateDB server and return the result."""
    url = HTTP_URL
    if url.endswith("/"):
        url = url.removesuffix("/")

    response = httpx.post(f"{url}/_sql", json={"stmt": query}, timeout=Settings.http_timeout())
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
        message = shorten(result["error"]["message"], Settings.max_chars())
        raise CrateError(f"{message} (error code {result['error']['code']})")
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


def query_sql(query: str, limit: t.Optional[t.Annotated[int, Field(ge=1)]] = None) -> BoundedResult:
    """
    Execute an SQL query on CrateDB and return the results.
    Select only the columns you need (avoid `SELECT *`) and,
    where appropriate, add a `LIMIT` clause to keep result sets concise.
    The result holds at most as many rows as the server's row cap, 1000 by
    default, or as `limit` when it is lower. `rows_returned` counts its
    rows. When rows are cut, `truncated` is true and `note` says why.
    """
    with read_only_check():
        permitted = sql_is_permitted(query)
    if not permitted:
        raise ToolError("Only queries that have a SELECT statement are allowed.")
    result = run_query(query)
    rows, note = bound_rows(
        result["rows"],
        Settings.max_rows(),
        "row",
        "Narrow the query with a WHERE clause or an aggregation, or read the rows in parts "
        "with LIMIT and OFFSET in the query.",
        "Filter or aggregate the query, or select fewer or shorter columns.",
        limit,
    )
    return BoundedResult(**{**result, "rows": rows, "truncated": note is not None, "note": note})


def row_chars(row: t.Any) -> int:
    """Count the characters of `row` as the server sends it: compact JSON with unescaped text."""
    return len(json.dumps(row, default=str, ensure_ascii=False, separators=(",", ":")))


def bound_rows(
    rows: t.List[t.Any],
    row_cap: int,
    noun: str,
    advice: str = "",
    char_advice: str = "",
    limit: t.Optional[int] = None,
) -> t.Tuple[t.List[t.Any], t.Optional[str]]:
    """
    Keep the first rows, at most `row_cap`, or `limit` when it is lower, and no more than fit
    in the character cap. Say which cut them, with `char_advice` in place of `advice` for the
    character cap and no advice for `limit`.
    """
    row_cap, char_cap = max(1, row_cap), Settings.max_chars()
    reason = f"an answer holds at most {row_cap} of them"
    if limit is not None and limit <= row_cap:
        row_cap, advice, reason = limit, "", f"`limit` asks for {limit} of them"
    kept = rows[:row_cap]
    size = 0
    for count, row in enumerate(kept):
        size += row_chars(row)
        if size > char_cap:
            kept, advice = kept[:count], char_advice or advice
            reason = f"an answer holds at most {char_cap} characters"
            if not kept:
                reason += f", and the first {noun} alone holds more"
            break
    if len(kept) == len(rows):
        return kept, None
    note = f"Only {len(kept)} of {len(rows)} {noun}s are shown, because {reason}."
    return kept, " ".join(filter(None, [note, advice]))


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
    if not documentation_index.url_permitted(link):
        raise ValueError(f"Link is not permitted: {link}")
    response = documentation_index.client.get(
        link, timeout=Settings.http_timeout(), follow_redirects=True
    )
    if not documentation_index.url_permitted(str(response.url)):
        raise ValueError(f"Link redirects to a location that is not permitted: {response.url}")
    response.raise_for_status()
    return response.text


# ------------------------------------------
#            Health / Status
# ------------------------------------------
def get_cluster_health() -> BoundedResult:
    """Return the health of each table and partition from `sys.health`, most severe first."""
    result = query_result(Queries.HEALTH)
    rows, note = bound_rows(
        result["rows"],
        Settings.max_rows(),
        "row",
        "Query sys.health with query_sql, filtered by table_schema, table_name or health, "
        "for the others.",
    )
    return BoundedResult(**{**result, "rows": rows, "truncated": note is not None, "note": note})
