import contextlib
import contextvars
import json
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


class BoundedResult(CrateResult):
    truncated: t.Optional[bool] = absent()
    note: t.Optional[str] = absent()


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


MAX_ROWS_CEILING = 1000


def row_ceiling() -> int:
    """Return the most rows `max_rows` may ask for: 1000, or the configured cap when larger."""
    return max(MAX_ROWS_CEILING, Settings.max_rows())


def query_sql(query: str, max_rows: t.Optional[int] = None) -> BoundedResult:
    """
    Execute an SQL query on CrateDB and return the results.
    Select only the columns you need (avoid `SELECT *`) and,
    where appropriate, add a `LIMIT` clause to keep result sets concise.
    The result holds at most 100 rows, or the server's configured cap,
    unless `max_rows` asks for more, up to 1000 or the configured cap,
    whichever is larger. When rows are cut,
    `truncated` is true and `note` says why.
    """
    with read_only_check():
        permitted = sql_is_permitted(query)
    if not permitted:
        raise ToolError("Only queries that have a SELECT statement are allowed.")
    return BoundedResult(**bound_result(run_query(query), max_rows))


def row_chars(row: t.Any) -> int:
    return len(json.dumps(row, default=str))


def cap_rows(rows: t.List[t.Any], row_cap: int) -> t.List[t.Any]:
    """Keep the first rows, at most `row_cap` and no more than fit in the character cap."""
    rows = rows[:row_cap]
    size = 0
    for count, row in enumerate(rows):
        size += row_chars(row)
        if size > Settings.max_chars():
            return rows[:count]
    return rows


def cut_note(rows: t.List[t.Any], kept: int, row_cap: int, noun: str) -> str:
    """Say why only the first `kept` of `rows` are shown."""
    char_cap = Settings.max_chars()
    if not kept:
        return (
            f"No {noun}s are shown, because the first {noun} alone holds "
            f"{row_chars(rows[0])} characters, more than the cap of {char_cap}."
        )
    shown = f"Only the first {kept} of {len(rows)} {noun}s are shown"
    if kept < min(row_cap, len(rows)):
        return f"{shown}, because the next {noun} would pass {char_cap} characters."
    return f"{shown}, because the cap is {row_cap} {noun if row_cap == 1 else noun + 's'}."


def bound_rows(
    rows: t.List[t.Any],
    noun: str,
    advice: str = "",
    row_cap: t.Optional[int] = None,
    advice_on_shown: str = "",
) -> t.Tuple[t.List[t.Any], t.Optional[str]]:
    """
    Keep the first rows within the row and character caps, and say why when some are cut.
    `advice_on_shown` speaks of the rows shown, so it is left out when none is shown.
    """
    if row_cap is None:
        row_cap = max(1, Settings.max_rows())
    kept = cap_rows(rows, row_cap)
    if len(kept) == len(rows):
        return kept, None
    note = [cut_note(rows, len(kept), row_cap, noun), advice_on_shown if kept else "", advice]
    return kept, " ".join(filter(None, note))


def bound_result(result: dict, max_rows: t.Optional[int] = None) -> dict:
    """Cut the rows of a query result to the row and character caps, and say when it did."""
    row_cap = Settings.max_rows() if max_rows is None else min(max_rows, row_ceiling())
    row_cap = max(1, row_cap)

    rows = cap_rows(result["rows"], row_cap)
    bounded = {**result, "rows": rows, "truncated": len(rows) < len(result["rows"])}
    if bounded["truncated"]:
        if not rows:
            advice = "Select fewer columns or shorter values."
        elif len(rows) < min(row_cap, len(result["rows"])):
            advice = "Select fewer or shorter columns, or filter or aggregate the query."
        else:
            advice = "Filter or aggregate the query"
            if row_cap < row_ceiling():
                advice += f", or ask for up to {row_ceiling()} rows with max_rows"
            advice += "."
        bounded["note"] = f"{cut_note(result['rows'], len(rows), row_cap, 'row')} {advice}"
    return bounded


def fit_text(text: str, fits: t.Callable[[str], bool], mark: str = "…") -> str:
    """Return the longest start of `text` that still fits when ended with `mark`, or ""."""
    kept, longest = 0, min(len(text), Settings.max_chars())
    while kept < longest:
        middle = (kept + longest + 1) // 2
        if fits(text[:middle] + mark):
            kept = middle
        else:
            longest = middle - 1
    return text[:kept] + mark if kept else ""


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


class DocumentationPages(BaseModel):
    model_config = ConfigDict(json_schema_extra=declare_present_types)

    pages: t.List[DocumentationLink]
    truncated: bool
    note: t.Optional[str] = absent()


def get_cratedb_documentation_index() -> DocumentationPages:
    """
    Return the table of contents for the curated CrateDB documentation index.
    Use it whenever you need to verify CrateDB-specific details or syntax.
    """
    pages = [DocumentationLink(**item) for item in documentation_index.items()]
    shown, note = bound_rows(
        [page.model_dump() for page in pages],
        "page",
        row_cap=len(pages),
        advice_on_shown="Choose from the pages shown.",
    )
    return DocumentationPages(pages=pages[: len(shown)], truncated=note is not None, note=note)


class DocumentationPage(BaseModel):
    model_config = ConfigDict(json_schema_extra=declare_present_types)

    text: str
    truncated: bool
    note: t.Optional[str] = absent()


def page_part(text: str, start: int) -> DocumentationPage:
    """Cut a page to the character cap from `start`, and say where the next part starts."""
    if start and start >= len(text):
        raise ToolError(f"The page holds {len(text)} characters, so `start` must be lower.")
    char_cap = Settings.max_chars()
    rest = text[start:]
    if row_chars(rest) <= char_cap:
        return DocumentationPage(text=rest, truncated=False)
    part = fit_text(rest, lambda part: row_chars(part) <= char_cap, mark="")
    if not part:
        note = f"No text is shown, because the cap of {char_cap} characters leaves no room for it."
    else:
        end = start + len(part)
        note = (
            f"Only characters {start} to {end} of {len(text)} are shown, to keep the answer "
            f"under the limit. Call again with start={end} to read on."
        )
    return DocumentationPage(text=part, truncated=True, note=note)


def fetch_cratedb_docs(link: str, start: int = 0) -> DocumentationPage:
    """
    Given a `link` returned by `get_cratedb_documentation_index`,
    fetch the content of that documentation page. Content can be
    quoted verbatim when answering questions about CrateDB. A long
    page comes in parts; `note` says which `start` reads on.
    """
    return page_part(documentation_index.fetch(link), max(0, start))


# ------------------------------------------
#            Health / Status
# ------------------------------------------
def get_cluster_health() -> BoundedResult:
    """Return the health of each table and partition from `sys.health`, most severe first."""
    result = query_result(Queries.HEALTH)
    rows, note = bound_rows(
        result["rows"],
        "row",
        "Query sys.health with query_sql, filtered by table_schema, table_name or health, "
        "for the others.",
        advice_on_shown="Rows come most severe first, so none of the others is worse than "
        "the last one shown.",
    )
    return BoundedResult(**{**result, "rows": rows, "truncated": note is not None, "note": note})
