import contextlib
import json
import typing as t

import httpx
from fastmcp.exceptions import ToolError
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlparse.engine import grouping
from sqlparse.exceptions import SQLParseError

from cratedb_mcp.knowledge import DocumentationIndex, Queries
from cratedb_mcp.settings import Settings
from cratedb_mcp.util.http_client import read_at_most, uncompressed_client
from cratedb_mcp.util.sql import SqlStatementClassifier, sql_is_permitted

MAX_RESPONSE_BYTES = 5_000_000
cratedb_client = uncompressed_client()


class CrateError(ToolError):
    """An error CrateDB answered to a statement."""


class StatementTimeout(ToolError):
    """CrateDB did not answer a statement within the HTTP timeout."""


class AnswerTooLarge(ToolError):
    """CrateDB's answer is larger than the server reads."""


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
def sql_endpoint() -> t.Tuple[httpx.URL, t.Optional[t.Tuple[str, str]]]:
    """Return the URL of CrateDB's SQL endpoint without the user part, and the credentials."""
    cluster = Settings.cluster_url()
    path = cluster.path.rstrip("/") + "/_sql"
    url = cluster.copy_with(userinfo=b"", path=path)
    return url, (cluster.username, cluster.password) if cluster.userinfo else None


def query_cratedb(query: str, args: t.Optional[t.List[t.Any]] = None) -> dict:
    """Send the SQL `query` to the configured CrateDB server and return its answer."""
    timeout = Settings.http_timeout()
    url, auth = sql_endpoint()
    payload: t.Dict[str, t.Any] = {"stmt": query}
    if args is not None:
        payload["args"] = args
    with cratedb_client.stream("POST", url, json=payload, auth=auth, timeout=timeout) as response:
        body = read_at_most(response, MAX_RESPONSE_BYTES)
        if body is None:
            raise AnswerTooLarge(
                f"The answer from CrateDB is larger than the {MAX_RESPONSE_BYTES:,} bytes "
                "the server reads."
            )
        try:
            return json.loads(body)
        except ValueError as e:
            text = shorten(body.decode(errors="replace").strip(), 200)
            raise ToolError(
                f"CrateDB answered HTTP {response.status_code}" + (f": {text}" if text else ".")
            ) from e


def query_result(query: str, args: t.Optional[t.List[t.Any]] = None) -> dict:
    """Run `query` with bound `args` and return its result, raising CrateDB's error."""
    try:
        result = query_cratedb(query, args)
    except httpx.TimeoutException as e:
        raise StatementTimeout(
            f"CrateDB did not answer within the {Settings.http_timeout():g}-second timeout."
        ) from e
    if "error" in result:
        message = shorten(result["error"]["message"], Settings.max_chars())
        raise CrateError(f"{message} (error code {result['error']['code']})")
    return result


def query_rows(query: str, args: t.Optional[t.List[t.Any]] = None) -> t.List[t.List[t.Any]]:
    """Run `query` with bound `args` and return its rows."""
    return query_result(query, args)["rows"]


def run_query(query: str) -> dict:
    """Run a query written by the model, and advise narrowing one that is too slow or too large."""
    try:
        return query_result(query)
    except StatementTimeout as e:
        raise ToolError(
            f"The query did not finish within the {Settings.http_timeout():g}-second timeout. "
            "Narrow it with a WHERE clause, an aggregation or a LIMIT instead of running it again."
        ) from e
    except AnswerTooLarge as e:
        raise ToolError(
            f"The result is larger than the {MAX_RESPONSE_BYTES:,} bytes the server reads. "
            "Add a LIMIT, select fewer columns, or aggregate the query."
        ) from e


def parser_limit_advice(error: SQLParseError) -> str:
    """Name the `sqlparse` limit a statement passed, in the words a model can act on."""
    message = str(error)
    if message.startswith("Maximum grouping depth"):
        return (
            f"it nests parentheses or subqueries more than {grouping.MAX_GROUPING_DEPTH} levels "
            "deep. Flatten the nesting, or split it into smaller queries."
        )
    if message.startswith("Maximum number of tokens"):
        return (
            f"it holds more than {grouping.MAX_GROUPING_TOKENS:,} tokens in one list or clause, "
            "and every value, name, operator and comma counts. For a long list of values, "
            "filter by a range, join against a table, or run several smaller queries."
        )
    return f"{message.rstrip('.')}. Shorten it, or split it into smaller queries."


@contextlib.contextmanager
def read_only_check() -> t.Iterator[None]:
    """Fail the call when the read-only check cannot analyze a statement."""
    try:
        yield
    except SQLParseError as e:
        raise ToolError(
            f"The read-only check cannot analyze this statement: {parser_limit_advice(e)}"
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
        keyword = SqlStatementClassifier(query).keyword
    if not permitted:
        raise ToolError(
            "Only one SELECT, WITH, VALUES or SHOW statement, or an EXPLAIN of a SELECT, "
            "WITH or VALUES statement, is allowed."
        )
    result = run_query(query)
    if keyword == "EXPLAIN":
        return BoundedResult(**bound_plan(result))
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


def fit_text(text: str, fits: t.Callable[[str], bool]) -> str:
    """Return the longest start of `text` that still fits when ended with "…", or ""."""
    kept, longest = 0, min(len(text), Settings.max_chars())
    while kept < longest:
        middle = (kept + longest + 1) // 2
        if fits(text[:middle] + "…"):
            kept = middle
        else:
            longest = middle - 1
    return text[:kept] + "…" if kept else ""


def bound_plan(plan: dict) -> dict:
    """Cut a plan that passes the character cap to its final step, and that step to the cap."""
    char_cap = Settings.max_chars()
    if sum(row_chars(row) for row in plan["rows"]) <= char_cap:
        return {**plan, "truncated": False}
    final = plan["rows"][-1]
    rows = [final]
    if row_chars(final) > char_cap:
        *step, cell = final
        if not isinstance(cell, str):
            cell = json.dumps(cell, ensure_ascii=False, separators=(",", ":"))
        shown = fit_text(cell, lambda part: row_chars([*step, part]) <= char_cap)
        rows = [[*step, shown]] if shown else []
    note = (
        f"The plan is longer than the cap of {char_cap} characters, so the answer holds as "
        "much of its final step as fits. A narrower query, or one explained without "
        "`analyze` or `verbose`, gives a shorter plan."
    )
    return {**plan, "rows": rows, "truncated": True, "note": note}


def explain_query(
    query: str, analyze: bool = False, verbose: bool = False, costs: bool = True
) -> BoundedResult:
    """
    Show how CrateDB runs a SELECT query, to find out why it is slow.
    `costs` adds the planner's row estimates, and `verbose` shows the plan
    after each optimizer step. `analyze` runs the query and returns its
    timings per shard, with the Lucene query each shard used. In that output,
    `MatchAllDocsQuery` and `GenericFunctionQuery` mean a full table scan,
    often a filter that is not pushed down to the index. With `analyze`,
    CrateDB ignores `costs` and cannot show `verbose`.
    """
    if analyze and verbose:
        raise ToolError("CrateDB cannot combine `analyze` and `verbose`; choose one.")
    with read_only_check():
        permitted = sql_is_permitted(query)
        keyword = SqlStatementClassifier(query).keyword
    if keyword == "EXPLAIN":
        raise ToolError(
            "Pass the query without EXPLAIN; `analyze`, `verbose` and `costs` set its options."
        )
    if keyword not in ("SELECT", "WITH", "VALUES") or not permitted:
        raise ToolError("Only one SELECT, WITH or VALUES statement can be explained.")
    if analyze:
        options = "ANALYZE true"
    else:
        options = f"COSTS {str(costs).lower()}, VERBOSE {str(verbose).lower()}"
    return BoundedResult(**bound_plan(run_query(f"EXPLAIN ({options}) {query}")))


SYSTEM_SCHEMAS = ("information_schema", "pg_catalog", "sys", "blob")
TABLE_KINDS = {"BASE TABLE": "table", "VIEW": "view", "FOREIGN": "foreign table"}


class SchemaInfo(BaseModel):
    schema_name: str
    tables: int
    views: int


class SchemaList(BaseModel):
    model_config = ConfigDict(json_schema_extra=declare_present_types)

    schemas: t.List[SchemaInfo]
    truncated: bool
    note: t.Optional[str] = absent()


class TableRef(BaseModel):
    name: str
    kind: str


class TableList(BaseModel):
    model_config = ConfigDict(json_schema_extra=declare_present_types)

    tables: t.List[TableRef]
    truncated: bool
    note: t.Optional[str] = absent()


class TableDescription(BaseModel):
    schema_name: str
    name: str
    kind: str
    definition: str
    primary_shards: t.Optional[int] = None
    records: t.Optional[int] = None
    size_bytes: t.Optional[int] = None
    partitions: t.Optional[int] = None
    truncated: bool = False
    note: t.Optional[str] = None


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def exclude_system_schemas(column: str) -> t.Tuple[str, t.List[t.Any]]:
    return f"{column} NOT IN ({', '.join('?' * len(SYSTEM_SCHEMAS))})", list(SYSTEM_SCHEMAS)


def list_schemas(include_system: bool = False) -> SchemaList:
    """
    List the schemas that hold tables or views, with how many of each.
    Start here to find out where the data lives. The system schemas
    information_schema, pg_catalog, sys and blob are left out unless
    `include_system` is true.
    """
    where = ""
    args: t.List[t.Any] = []
    if not include_system:
        condition, args = exclude_system_schemas("table_schema")
        where = f"WHERE {condition}"
    rows = query_rows(Queries.SCHEMAS.format(where=where), args)
    schemas = [SchemaInfo(schema_name=row[0], tables=row[1], views=row[2]) for row in rows]
    shown, note = bound_rows(
        [schema.model_dump() for schema in schemas],
        Settings.max_rows(),
        "schema",
        "Query information_schema.tables with query_sql for the others.",
    )
    return SchemaList(schemas=schemas[: len(shown)], truncated=note is not None, note=note)


def list_tables(schema: str, pattern: t.Optional[str] = None) -> TableList:
    """
    List the tables and views of one schema, by name and kind.
    `pattern` filters the names with SQL LIKE syntax, for example `sensor%`.
    Use `describe_table` next to see the columns of one of them.
    """
    args = [schema]
    condition = ""
    if pattern:
        condition = "AND table_name LIKE ?"
        args.append(pattern)
    rows = query_rows(Queries.TABLES.format(pattern=condition), args)
    tables = [TableRef(name=row[0], kind=TABLE_KINDS.get(row[1], row[1].lower())) for row in rows]
    shown, note = bound_rows(
        [table.model_dump() for table in tables],
        Settings.max_rows(),
        "table",
        "Narrow the list with `pattern`, or query information_schema.tables with query_sql.",
    )
    return TableList(tables=tables[: len(shown)], truncated=note is not None, note=note)


def describe_table(schema: str, table: str) -> TableDescription:
    """
    Describe one table or view. For a table, return its CREATE TABLE statement
    (columns, types, primary key, sharding and partitioning) with its primary
    shard count, record count, size in bytes and partition count. For a view,
    return its query. For a system table, return its columns and types.
    """
    description = table_description(schema, table)
    char_cap = Settings.max_chars()
    if row_chars(description.definition) <= char_cap:
        return description
    description.definition = fit_text(
        description.definition, lambda part: row_chars(part) <= char_cap
    )
    description.truncated = True
    cut = (
        f"The definition is cut to the cap of {char_cap} characters. Read the columns from "
        "information_schema.columns, or a view's query from information_schema.views, "
        "with query_sql."
    )
    description.note = " ".join(filter(None, [cut, description.note]))
    return description


def table_description(schema: str, table: str) -> TableDescription:
    """Read the definition of one table or view, and the storage counts of a table."""
    rows = query_rows(Queries.TABLE_TYPE, [schema, table])
    if not rows:
        raise ToolError(f"Table or view not found: {schema}.{table}")
    kind = TABLE_KINDS.get(rows[0][0], rows[0][0].lower())

    if kind == "view":
        definition = query_rows(Queries.VIEW_DEFINITION, [schema, table])[0][0]
        return TableDescription(schema_name=schema, name=table, kind=kind, definition=definition)

    if kind != "table" or schema in SYSTEM_SCHEMAS:
        columns = query_rows(Queries.COLUMNS, [schema, table])
        definition = "\n".join(f"{name} {data_type}" for name, data_type in columns)
        return TableDescription(schema_name=schema, name=table, kind=kind, definition=definition)

    statement = f"SHOW CREATE TABLE {quote_identifier(schema)}.{quote_identifier(table)}"
    description = TableDescription(
        schema_name=schema, name=table, kind=kind, definition=query_rows(statement)[0][0]
    )
    # A user granted access to single schemas cannot read `sys.shards`.
    try:
        storage = query_rows(Queries.TABLE_STORAGE, [schema, table])[0]
    except CrateError as e:
        description.note = (
            "The shard, record, size and partition counts are missing, because reading "
            f"sys.shards failed: {e}"
        )
        return description
    (
        description.primary_shards,
        description.records,
        description.size_bytes,
        description.partitions,
    ) = storage
    return description


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
