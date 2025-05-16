import httpx
from mcp.server.fastmcp import FastMCP

from .knowledge import DocumentationIndex, Queries
from .settings import HTTP_TIMEOUT, HTTP_URL
from .util.sql import sql_is_permitted

# Load CrateDB documentation outline.
documentation_index = DocumentationIndex()

# Create FastMCP application object.
mcp = FastMCP("cratedb-mcp")


def query_cratedb(query: str) -> list[dict]:
    return httpx.post(f'{HTTP_URL}/_sql', json={'stmt': query}, timeout=HTTP_TIMEOUT).json()


@mcp.tool(description="Send a SQL query to CrateDB, only 'SELECT' queries are allows, queries that"
                      " modify data, columns or are otherwise deemed un-safe are rejected.")
def query_sql(query: str):
    if not sql_is_permitted(query):
        raise ValueError('Only queries that have a SELECT statement are allowed.')
    return query_cratedb(query)

@mcp.tool(description='Gets an index with CrateDB documentation links to fetch, should download docs'
                      ' before answering questions. Has documentation title, description, and link.')
def get_cratedb_documentation_index():
    return documentation_index.items()

@mcp.tool(description='Downloads the latest CrateDB documentation piece by link.'
                      ' Only used to download CrateDB docs.')
def fetch_cratedb_docs(link: str):
    """Fetches a CrateDB documentation link."""
    if not documentation_index.url_permitted(link):
        raise ValueError(f'Link is not permitted: {link}')
    return documentation_index.client.get(link, timeout=HTTP_TIMEOUT).text

@mcp.tool(description="Returns an aggregation of all CrateDB's schema, tables and their metadata")
def get_table_metadata() -> list[dict]:
    """Returns an aggregation of schema:tables, e.g: {'doc': [{name:'mytable', ...}, ...]}

    The tables have metadata datapoints like replicas, shards, name, version, total_shards, total_records.
    """
    return query_cratedb(Queries.TABLES_METADATA)

@mcp.tool(description="Returns the health of a CrateDB cluster.")
def get_health() -> list[dict]:
    """Queries sys.health ordered by severity."""
    return query_cratedb(Queries.HEALTH)
