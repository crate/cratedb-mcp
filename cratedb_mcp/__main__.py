import hishel
import httpx
from mcp.server.fastmcp import FastMCP

from .knowledge import DOCUMENTATION_INDEX, Queries
from .settings import DOCS_CACHE_TTL, HTTP_URL

# Configure Hishel, an httpx client with caching.
# Define one hour of caching time.
controller = hishel.Controller(allow_stale=True)
storage = hishel.SQLiteStorage(ttl=DOCS_CACHE_TTL)
client = hishel.CacheClient(controller=controller, storage=storage)

# Create FastMCP application object.
mcp = FastMCP("cratedb-mcp")


def query_cratedb(query: str) -> list[dict]:
    return httpx.post(f'{HTTP_URL}/_sql', json={'stmt': query}).json()


@mcp.tool(description="Send a SQL query to CrateDB, only 'SELECT' queries are allows, queries that"
                      " modify data, columns or are otherwise deemed un-safe are rejected.")
def query_sql(query: str):
    if 'select' not in query.lower():
        raise ValueError('Only queries that have a SELECT statement are allowed.')
    return query_cratedb(query)

@mcp.tool(description='Gets an index with CrateDB documentation links to fetch, should download docs'
                      ' before answering questions. Has documentation name, description and link.')
def get_cratedb_documentation_index():
    return DOCUMENTATION_INDEX

@mcp.tool(description='Downloads the latest CrateDB documentation piece by link.'
                      ' Only used to download CrateDB docs.')
def fetch_cratedb_docs(link: str):
    """Fetches a CrateDB documentation link from GitHub raw content."""
    if 'https://raw.githubusercontent.com/crate/crate/' not in link:
        raise ValueError('Only github cratedb links can be fetched.')
    return client.get(link).text

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
