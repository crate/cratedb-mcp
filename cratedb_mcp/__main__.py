import importlib.resources

from cratedb_about.instruction import GeneralInstructions
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

instructions_general = GeneralInstructions().render()
instructions_mcp = (importlib.resources.files("cratedb_mcp") / "instructions.md").read_text()

# Create FastMCP application object.
mcp: FastMCP = FastMCP(
    name=__appname__,
    instructions=instructions_mcp + instructions_general,
)


# ------------------------------------------
#              Text-to-SQL
# ------------------------------------------
mcp.add_tool(
    Tool.from_function(
        fn=get_table_metadata,
        description="Return column schema and metadata for all tables stored in CrateDB. "
        "Use it to inquire entities you don't know about.",
        tags={"text-to-sql"},
    )
)
mcp.add_tool(
    Tool.from_function(
        fn=query_sql,
        description="Send an SQL query to CrateDB and return results. "
        "Only 'SELECT' queries are allowed.",
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
