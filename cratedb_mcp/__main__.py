import httpx
from fastmcp import FastMCP

from . import __appname__
from .knowledge import DocumentationIndex, Queries
from .settings import HTTP_URL, Settings
from .util.sql import sql_is_permitted

# Load CrateDB documentation outline.
documentation_index = DocumentationIndex()

# Create FastMCP application object.
mcp: FastMCP = FastMCP(__appname__)


# ------------------------------------------
#              Text-to-SQL
# ------------------------------------------


def query_cratedb(query: str) -> list[dict]:
    """Sends a `query` to the set `$CRATEDB_CLUSTER_URL`"""
    url = HTTP_URL
    if url.endswith("/"):
        url = url.removesuffix("/")

    return httpx.post(f"{url}/_sql", json={"stmt": query}, timeout=Settings.http_timeout()).json()


@mcp.tool(description="Send an SQL query to CrateDB. Only 'SELECT' queries are allowed.")
def query_sql(query: str):
    if not sql_is_permitted(query):
        raise PermissionError("Only queries that have a SELECT statement are allowed.")
    return query_cratedb(query)


@mcp.tool(description="Return an aggregation of all CrateDB's schema, tables and their metadata.")
def get_table_metadata() -> list[dict]:
    """
    Return an aggregation of schema:tables, e.g.: {'doc': [{name:'mytable', ...}, ...]}

    The tables have metadata datapoints like replicas, shards,
    name, version, total_shards, total_records.
    """
    return query_cratedb(Queries.TABLES_METADATA)


@mcp.tool(description="Return the health of the CrateDB cluster.")
def get_cluster_health() -> list[dict]:
    """Query sys.health ordered by severity."""
    return query_cratedb(Queries.HEALTH)


# ------------------------------------------
#          Documentation Inquiry
# ------------------------------------------


@mcp.tool(
    description="Get an index of CrateDB documentation links for fetching. "
    "Should download docs before answering questions. "
    "Has documentation title, description, and link."
)
def get_cratedb_documentation_index():
    return documentation_index.items()


@mcp.tool(description="Download individual CrateDB documentation pages by link.")
def fetch_cratedb_docs(link: str):
    """Fetch a CrateDB documentation link."""
    if not documentation_index.url_permitted(link):
        raise ValueError(f"Link is not permitted: {link}")
    return documentation_index.client.get(link, timeout=Settings.http_timeout()).text
