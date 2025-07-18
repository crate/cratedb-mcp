from fastmcp import FastMCP
from fastmcp.tools import Tool

from . import __appname__
from .tool import (
    fetch_cratedb_docs,
    get_cluster_health,
    get_cratedb_documentation_index,
    get_table_metadata,
    query_sql,
)

# Create FastMCP application object.
mcp: FastMCP = FastMCP(__appname__)


# ------------------------------------------
#            Health / Status
# ------------------------------------------
mcp.add_tool(
    Tool.from_function(
        fn=get_cluster_health,
        description="Return the health of the CrateDB cluster.",
        tags={"health", "monitoring", "status"},
    )
)


# ------------------------------------------
#              Text-to-SQL
# ------------------------------------------
mcp.add_tool(
    Tool.from_function(
        fn=query_sql,
        description="Send an SQL query to CrateDB. Only 'SELECT' queries are allowed.",
        tags={"text-to-sql"},
    )
)
mcp.add_tool(
    Tool.from_function(
        fn=get_table_metadata,
        description="Return an aggregation of all CrateDB's schema, tables and their metadata.",
        tags={"text-to-sql"},
    )
)


# ------------------------------------------
#          Documentation inquiry
# ------------------------------------------
mcp.add_tool(
    Tool.from_function(
        fn=get_cratedb_documentation_index,
        description="Get an index of CrateDB documentation links for fetching. "
        "Should download docs before answering questions. "
        "Has documentation title, description, and link.",
        tags={"documentation"},
    )
)
mcp.add_tool(
    Tool.from_function(
        fn=fetch_cratedb_docs,
        description="Download individual CrateDB documentation pages by link.",
        tags={"documentation"},
    )
)
