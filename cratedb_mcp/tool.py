import json
import typing as t

import httpx
from pydantic import BaseModel

from cratedb_mcp.knowledge import DocumentationIndex, Queries
from cratedb_mcp.settings import HTTP_URL, Settings
from cratedb_mcp.util.sql import sql_is_permitted


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


def query_rows(query: str, args: t.Optional[t.List[t.Any]] = None) -> t.List[t.List[t.Any]]:
    """Run `query` with bound `args` and return its rows, raising CrateDB's error message."""
    response = query_cratedb(query, args)
    if "error" in response:
        raise RuntimeError(response["error"]["message"])
    return response["rows"]


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


def query_sql(query: str, max_rows: t.Optional[int] = None) -> dict:
    """
    Execute an SQL query on CrateDB and return the results.
    Select only the columns you need (avoid `SELECT *`) and,
    where appropriate, add a `LIMIT` clause to keep result sets concise.
    The result holds at most 100 rows, or the server's configured cap,
    unless `max_rows` asks for more, up to 1000. When rows are cut,
    `truncated` is true and `note` says why.
    """
    if not sql_is_permitted(query):
        raise PermissionError("Only queries that have a SELECT statement are allowed.")
    return bound_result(run_query(query), max_rows)


def row_chars(row: t.Any) -> int:
    return len(json.dumps(row, default=str))


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

    rows = result["rows"][:row_cap]
    size = 0
    for count, row in enumerate(rows):
        size += row_chars(row)
        if size > char_cap:
            rows = rows[:count]
            break

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
) -> dict:
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
    if not sql_is_permitted(query):
        raise PermissionError("Only queries that have a SELECT statement are allowed.")
    if analyze:
        options = "ANALYZE true"
    else:
        options = f"COSTS {str(costs).lower()}, VERBOSE {str(verbose).lower()}"
    advice = "Narrow the query."
    if analyze:
        advice = "Explain it without `analyze`, or narrow the query."
    plan = run_query(f"EXPLAIN ({options}) {query}")
    return bound_result(plan, MAX_ROWS_CEILING, advice, advice)


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
def get_cluster_health() -> dict:
    """Return the health of the CrateDB cluster by querying `sys.health` ordered by severity."""
    return query_cratedb(Queries.HEALTH)
