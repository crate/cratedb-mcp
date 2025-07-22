import httpx

from cratedb_mcp.knowledge import DocumentationIndex, Queries
from cratedb_mcp.settings import HTTP_URL, Settings
from cratedb_mcp.util.sql import sql_is_permitted


# ------------------------------------------
#              Text-to-SQL
# ------------------------------------------
def query_cratedb(query: str) -> dict:
    """Sends a `query` to the set `$CRATEDB_CLUSTER_URL`"""
    url = HTTP_URL
    if url.endswith("/"):
        url = url.removesuffix("/")

    return httpx.post(f"{url}/_sql", json={"stmt": query}, timeout=Settings.http_timeout()).json()


def query_sql(query: str) -> dict:
    if not sql_is_permitted(query):
        raise PermissionError("Only queries that have a SELECT statement are allowed.")
    return query_cratedb(query)


def get_table_metadata() -> dict:
    """
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
    """Get curated CrateDB documentation index."""
    return documentation_index.items()


def fetch_cratedb_docs(link: str) -> str:
    """Fetch a CrateDB documentation link."""
    if not documentation_index.url_permitted(link):
        raise ValueError(f"Link is not permitted: {link}")
    return documentation_index.client.get(link, timeout=Settings.http_timeout()).text


# ------------------------------------------
#            Health / Status
# ------------------------------------------
def get_cluster_health() -> dict:
    """Query sys.health ordered by severity."""
    return query_cratedb(Queries.HEALTH)
