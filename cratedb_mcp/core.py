from typing import Optional

from fastmcp import FastMCP
from fastmcp.tools import Tool

from cratedb_mcp.prompt import InstructionsPrompt

from . import __appname__, __version__
from .tool import (
    fetch_cratedb_docs,
    get_cluster_health,
    get_cratedb_documentation_index,
    get_table_columns,
    get_table_metadata,
    query_sql,
)


class CrateDbMcp:
    """
    Small wrapper around the FastMCP API to provide instructions prompt at runtime.
    """

    def __init__(
        self,
        mcp: Optional[FastMCP] = None,
        instructions: Optional[str] = None,
        conventions: Optional[str] = None,
    ) -> None:
        prompt = InstructionsPrompt(instructions=instructions, conventions=conventions)
        self.mcp = mcp or FastMCP(
            name=__appname__,
            version=__version__,
            instructions=prompt.render(),
        )
        self.add_tools()

    def add_tools(self):
        """Register all CrateDB MCP tools with the FastMCP instance."""
        # ------------------------------------------
        #              Text-to-SQL
        # ------------------------------------------
        self.mcp.add_tool(
            Tool.from_function(
                fn=query_sql,
                description=query_sql.__doc__,
                tags={"text-to-sql"},
            )
        )
        self.mcp.add_tool(
            Tool.from_function(
                fn=get_table_columns,
                description=get_table_columns.__doc__,
                tags={"text-to-sql"},
            )
        )
        self.mcp.add_tool(
            Tool.from_function(
                fn=get_table_metadata,
                description=get_table_metadata.__doc__,
                tags={"text-to-sql"},
            )
        )

        # ------------------------------------------
        #          Documentation inquiry
        # ------------------------------------------
        self.mcp.add_tool(
            Tool.from_function(
                fn=get_cratedb_documentation_index,
                description=get_cratedb_documentation_index.__doc__,
                tags={"documentation"},
            )
        )
        self.mcp.add_tool(
            Tool.from_function(
                fn=fetch_cratedb_docs,
                description=fetch_cratedb_docs.__doc__,
                tags={"documentation"},
            )
        )

        # ------------------------------------------
        #            Health / Status
        # ------------------------------------------
        self.mcp.add_tool(
            Tool.from_function(
                fn=get_cluster_health,
                description=get_cluster_health.__doc__,
                tags={"health", "monitoring", "status"},
            )
        )

        return self
