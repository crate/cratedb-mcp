import json
import typing as t

import httpx
from pydantic import BaseModel, ConfigDict, Field

from cratedb_mcp.knowledge import DocumentationIndex, Queries
from cratedb_mcp.settings import HTTP_URL, Settings
from cratedb_mcp.util.sql import SqlStatementClassifier, sql_is_permitted


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


class CrateError(BaseModel):
    message: str
    code: int


class CrateResult(BaseModel):
    model_config = ConfigDict(extra="allow", json_schema_extra=declare_present_types)

    cols: t.Optional[t.List[str]] = absent()
    rows: t.Optional[t.List[t.List[t.Any]]] = absent()
    rowcount: t.Optional[int] = absent()
    duration: t.Optional[float] = absent()
    error: t.Optional[CrateError] = absent()


class BoundedResult(CrateResult):
    truncated: t.Optional[bool] = absent()
    note: t.Optional[str] = absent()


# ------------------------------------------
#              Text-to-SQL
# ------------------------------------------
def query_cratedb(query: str, args: t.Optional[t.List[t.Any]] = None) -> dict:
    """Send the SQL `query` to the configured CrateDB server and return the result."""
    url = HTTP_URL
    if url.endswith("/"):
        url = url.removesuffix("/")

    payload: t.Dict[str, t.Any] = {"stmt": query}
    if args is not None:
        payload["args"] = args
    return httpx.post(f"{url}/_sql", json=payload, timeout=Settings.http_timeout()).json()


def query_result(query: str, args: t.Optional[t.List[t.Any]] = None) -> dict:
    """Run `query` with bound `args` and return its result, raising CrateDB's error message."""
    response = query_cratedb(query, args)
    if "error" in response:
        raise RuntimeError(response["error"]["message"])
    return response


def query_rows(query: str, args: t.Optional[t.List[t.Any]] = None) -> t.List[t.List[t.Any]]:
    """Run `query` with bound `args` and return its rows."""
    return query_result(query, args)["rows"]


MAX_ROWS_CEILING = 1000


def run_query(query: str) -> dict:
    """Send a query written by the model, and answer a timeout with advice to narrow it."""
    try:
        return query_cratedb(query)
    except httpx.TimeoutException as e:
        raise TimeoutError(
            f"The query did not finish within the {Settings.http_timeout():g}-second timeout. "
            "Narrow it with a WHERE clause, an aggregation or a LIMIT instead of running it again."
        ) from e


def query_sql(query: str, max_rows: t.Optional[int] = None) -> BoundedResult:
    """
    Execute an SQL query on CrateDB and return the results.
    Select only the columns you need (avoid `SELECT *`) and,
    where appropriate, add a `LIMIT` clause to keep result sets concise.
    The result holds at most 100 rows, or the server's configured cap,
    unless `max_rows` asks for more, up to 1000. When rows are cut,
    `truncated` is true and `note` says why.
    """
    if not sql_is_permitted(query):
        raise PermissionError(
            "Only one SELECT, WITH, VALUES or SHOW statement, or an EXPLAIN of a SELECT, "
            "WITH or VALUES statement, is allowed."
        )
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


def bound_result(
    result: dict,
    max_rows: t.Optional[int] = None,
    char_advice: str = "Select fewer or shorter columns, or filter or aggregate the query.",
    first_row_advice: str = "Select fewer columns or shorter values.",
) -> dict:
    """Cut the rows of a query result to the row and character caps, and say when it did."""
    if "rows" not in result:
        return result
    row_cap = Settings.max_rows() if max_rows is None else max_rows
    row_cap = max(1, min(row_cap, MAX_ROWS_CEILING))
    char_cap = Settings.max_chars()

    rows = cap_rows(result["rows"], row_cap)
    bounded = {**result, "rows": rows, "truncated": len(rows) < len(result["rows"])}
    if bounded["truncated"]:
        shown = f"Only the first {len(rows)} of {len(result['rows'])} rows are shown"
        if not rows:
            bounded["note"] = (
                f"No rows are shown, because the first row alone holds "
                f"{row_chars(result['rows'][0])} characters, more than the cap of {char_cap}. "
                f"{first_row_advice}"
            )
        elif len(rows) < min(row_cap, len(result["rows"])):
            bounded["note"] = (
                f"{shown}, because the next row would pass {char_cap} characters. {char_advice}"
            )
        else:
            advice = "Filter or aggregate the query"
            if row_cap < MAX_ROWS_CEILING:
                advice += f", or ask for up to {MAX_ROWS_CEILING} rows with max_rows"
            bounded["note"] = f"{shown}, because the cap is {row_cap} rows. {advice}."
    return bounded


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
        raise ValueError("CrateDB cannot combine `analyze` and `verbose`; choose one.")
    keyword = SqlStatementClassifier(query).keyword
    if keyword == "EXPLAIN":
        raise ValueError(
            "Pass the query without EXPLAIN; `analyze`, `verbose` and `costs` set its options."
        )
    if keyword not in ("SELECT", "WITH", "VALUES") or not sql_is_permitted(query):
        raise PermissionError("Only one SELECT, WITH or VALUES statement can be explained.")
    if analyze:
        options = "ANALYZE true"
    else:
        options = f"COSTS {str(costs).lower()}, VERBOSE {str(verbose).lower()}"
    advice = "Narrow the query."
    if analyze:
        advice = "Explain it without `analyze`, or narrow the query."
    plan = run_query(f"EXPLAIN ({options}) {query}")
    return BoundedResult(**bound_result(plan, MAX_ROWS_CEILING, advice, advice))


SYSTEM_SCHEMAS = ("information_schema", "pg_catalog", "sys", "blob")
TABLE_KINDS = {"BASE TABLE": "table", "VIEW": "view", "FOREIGN": "foreign table"}


class SchemaInfo(BaseModel):
    schema_name: str
    tables: int
    views: int


class TableRef(BaseModel):
    name: str
    kind: str


class TableDescription(BaseModel):
    schema_name: str
    name: str
    kind: str
    definition: str
    primary_shards: t.Optional[int] = None
    records: t.Optional[int] = None
    size_bytes: t.Optional[int] = None
    partitions: t.Optional[int] = None


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def list_schemas(include_system: bool = False) -> t.List[SchemaInfo]:
    """
    List the schemas that hold tables or views, with how many of each.
    Start here to find out where the data lives. The system schemas
    information_schema, pg_catalog, sys and blob are left out unless
    `include_system` is true.
    """
    where, args = "", []
    if not include_system:
        where = f"WHERE table_schema NOT IN ({', '.join('?' * len(SYSTEM_SCHEMAS))})"
        args = list(SYSTEM_SCHEMAS)
    rows = query_rows(Queries.SCHEMAS.format(where=where), args)
    return [SchemaInfo(schema_name=row[0], tables=row[1], views=row[2]) for row in rows]


def list_tables(schema: str, pattern: t.Optional[str] = None) -> t.List[TableRef]:
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
    return [TableRef(name=row[0], kind=TABLE_KINDS.get(row[1], row[1].lower())) for row in rows]


def describe_table(schema: str, table: str) -> TableDescription:
    """
    Describe one table or view. For a table, return its CREATE TABLE statement
    (columns, types, primary key, sharding and partitioning) with its primary
    shard count, record count, size in bytes and partition count. For a view,
    return its query. For a system table, return its columns and types.
    """
    rows = query_rows(Queries.TABLE_TYPE, [schema, table])
    if not rows:
        raise ValueError(f"Table or view not found: {schema}.{table}")
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
    except RuntimeError:
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
def get_cluster_health() -> CrateResult:
    """Return the health of the CrateDB cluster by querying `sys.health` ordered by severity."""
    return CrateResult(**query_cratedb(Queries.HEALTH))


STATEMENT_CHARS = 1000
MAX_SINCE_MINUTES = 525_600
DATA_STATEMENT = r"(?is)\s*(SELECT|WITH|INSERT|UPDATE|DELETE)\b.*"


class Workload(BaseModel):
    model_config = ConfigDict(json_schema_extra=declare_present_types)

    user: t.Optional[str] = absent()
    stats_enabled: t.Optional[bool] = absent()
    jobs_log_size: t.Optional[int] = absent()
    cols: t.List[str]
    rows: t.List[t.List[t.Any]]
    truncated: bool
    note: t.Optional[str] = absent()


def cut_text(value: t.Any) -> t.Any:
    if isinstance(value, str) and len(value) > STATEMENT_CHARS:
        return value[:STATEMENT_CHARS] + "…"
    return value


def diagnose_workload(
    view: t.Literal["slow", "failed", "running", "summary"] = "slow",
    limit: int = 10,
    since_minutes: t.Optional[int] = None,
) -> Workload:
    """
    Statements that load the cluster. `slow`: finished, slowest first;
    `failed`: newest first, without statements CrateDB could not parse or
    resolve, such as one naming an unknown table; `running`: longest first.
    These three hold only queries and INSERT, UPDATE and DELETE statements,
    and only `user`'s own unless it is a superuser or has AL. `summary`:
    latencies in ms per statement type and node. `limit` (default 10) goes
    up to the row cap, 100 by default. `since_minutes` narrows `slow` and
    `failed`. Nodes keep their last `jobs_log_size` statements, dropping all
    past 5% of heap.
    """
    limit = max(1, min(limit, Settings.max_rows(), MAX_ROWS_CEILING))
    fetched = STATEMENT_CHARS + 1
    args: t.List[t.Any]
    if view == "summary":
        query, args = Queries.JOBS_METRICS, [limit]
    elif view == "running":
        # Leave this query out of its own answer.
        query, args = Queries.JOBS, [fetched, DATA_STATEMENT, Queries.JOBS, limit]
    else:
        conditions = ["classification['type'] IN ('SELECT', 'INSERT', 'UPDATE', 'DELETE')"]
        args = [fetched]
        if view == "failed":
            conditions.append("error IS NOT NULL")
        if since_minutes is not None:
            conditions.append("CAST(ended AS BIGINT) >= CAST(CURRENT_TIMESTAMP AS BIGINT) - ?")
            args.append(max(1, min(since_minutes, MAX_SINCE_MINUTES)) * 60_000)
        order = "ended" if view == "failed" else "duration_ms"
        query = Queries.JOBS_LOG.format(where=" AND ".join(conditions), order=order)
        args.append(limit)

    workload = Workload(cols=[], rows=[], truncated=False)
    # A user granted access to single schemas cannot read the `sys` tables.
    try:
        workload.stats_enabled, workload.jobs_log_size, workload.user = query_rows(Queries.STATS)[0]
        result = query_result(query, args)
    except RuntimeError as e:
        workload.note = f"No statements are shown, because reading the sys tables failed: {e}"
        return workload
    rows = [[cut_text(value) for value in row] for row in result["rows"]]
    workload.cols = result["cols"]
    workload.rows = cap_rows(rows, limit)
    workload.truncated = len(workload.rows) < len(rows)
    if workload.truncated and not workload.rows:
        workload.note = (
            f"No rows are shown, because the first row alone holds {row_chars(rows[0])} "
            f"characters, more than the cap of {Settings.max_chars()}."
        )
    elif workload.truncated:
        workload.note = (
            f"Only {len(workload.rows)} of {len(rows)} rows are shown, because the "
            f"next row would pass {Settings.max_chars()} characters."
        )
    return workload
