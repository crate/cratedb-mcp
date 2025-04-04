import os

import httpx

from mcp.server.fastmcp import FastMCP

from constants import Queries

mcp = FastMCP("cratedb-mcp")


def query_cratedb(query: str) -> list[dict]:
    return httpx.post(f'{os.getenv("CRATEDB_MCP_HTTP_URL")}/_sql', json={'stmt': query}).json()


@mcp.tool(description="Send a SQL query to CrateDB, only 'SELECT' queries are allows, queries that"
                      " modify data, columns or are otherwise deemed un-safe are rejected.")
def query_sql(query: str):
    if not 'select' in query.lower():
        raise ValueError('Only queries that have a SELECT statement are allowed.')
    return query_cratedb(query)

@mcp.tool(description='Gets an index with CrateDB documentation links to fetch, should download docs'
                      ' before answering questions. Has documentation name, description and link.')
def get_cratedb_documentation_index():
    doc_index = [
        {"name": "scalar functions",
         "description": "documentation about specific scalar/methods/functions for CrateDB SQL",
         "link": "https://raw.githubusercontent.com/crate/crate/refs/heads/5.10/docs/general/builtins/scalar-functions.rst"},
        {"name": "optimize query 101",
         "description": "documentation about optimizing CrateDB SQL statements",
         "link": "https://raw.githubusercontent.com/crate/cratedb-guide/9ab661997d7704ecbb63af9c3ee33535957e24e6/docs/performance/optimization.rst"
         }
    ]
    return doc_index

@mcp.tool(description='Downloads the latest CrateDB documentation piece by link.'
                      ' Only used to download CrateDB docs.')
def fetch_cratedb_docs(link: str):
    """Fetches a CrateDB documentation link from GitHub raw content."""
    if not 'https://raw.githubusercontent.com/crate/crate/' in link:
        raise ValueError('Only github cratedb links can be fetched.')
    return httpx.get(link).text

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
