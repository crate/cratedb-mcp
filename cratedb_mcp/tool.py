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


def query_sql(query: str) -> dict:
    """
    Execute an SQL query on CrateDB and return the results.
    Select only the columns you need (avoid `SELECT *`) and,
    where appropriate, add a `LIMIT` clause to keep result sets concise.
    """
    if not sql_is_permitted(query):
        raise PermissionError("Only queries that have a SELECT statement are allowed.")
    return query_cratedb(query)


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
    return query_cratedb(f"EXPLAIN ({options}) {query}")


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
