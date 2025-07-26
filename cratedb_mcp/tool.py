import httpx

from cratedb_mcp.knowledge import DocumentationIndex, Queries
from cratedb_mcp.settings import HTTP_URL, Settings
from cratedb_mcp.util.sql import sql_is_permitted


# ------------------------------------------
#              Text-to-SQL
# ------------------------------------------
def query_cratedb(query: str) -> dict:
    """Send the SQL `query` to the configured CrateDB server and return the result."""
    url = HTTP_URL
    if url.endswith("/"):
        url = url.removesuffix("/")

    return httpx.post(f"{url}/_sql", json={"stmt": query}, timeout=Settings.http_timeout()).json()


def query_sql(query: str) -> dict:
    """
    Execute an SQL query on CrateDB and return the results.
    Select only the columns you need (avoid `SELECT *`) and,
    where appropriate, add a `LIMIT` clause to keep result sets concise.
    """
    if not sql_is_permitted(query):
        raise PermissionError("Only queries that have a SELECT statement are allowed.")
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
        response[variant] = query_sql(query)
    return response


def get_table_metadata() -> dict:
    """
    Return table metadata for all tables stored in CrateDB.
    Return an aggregation of schema:tables, e.g.: {'doc': [{name:'mytable', ...}, ...]}

    The tables have metadata datapoints like replicas, shards,
    name, version, total_shards, total_records.
    """
    return query_cratedb(Queries.TABLES_METADATA)


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
    return documentation_index.client.get(link, timeout=Settings.http_timeout()).text


# ------------------------------------------
#            Health / Status
# ------------------------------------------
def get_cluster_health() -> dict:
    """Return the health of the CrateDB cluster by querying `sys.health` ordered by severity."""
    return query_cratedb(Queries.HEALTH)
