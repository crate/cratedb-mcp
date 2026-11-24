from typing import Optional

from fastmcp import FastMCP
from fastmcp.tools import Tool
from mcp.types import ToolAnnotations

from cratedb_mcp.prompt import InstructionsPrompt
from cratedb_mcp.settings import Settings

from . import __appname__, __version__
from .tool import (
    fetch_cratedb_docs,
    get_cluster_health,
    get_cratedb_documentation_index,
    get_table_columns,
    get_table_metadata,
    query_sql,
)

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
READ_ONLY_OPEN_WORLD = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
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
        read_only = not Settings.permit_all_statements()
        query_annotations = ToolAnnotations(
            readOnlyHint=read_only,
            destructiveHint=not read_only,
            idempotentHint=read_only,
            openWorldHint=False,
        )
        # ------------------------------------------
        #              Text-to-SQL
        # ------------------------------------------
        self.mcp.add_tool(
            Tool.from_function(
                fn=query_sql,
                description=query_sql.__doc__,
                title="Run SQL query",
                annotations=query_annotations,
                tags={"text-to-sql"},
            )
        )
        self.mcp.add_tool(
            Tool.from_function(
                fn=get_table_columns,
                description=get_table_columns.__doc__,
                title="List table columns",
                annotations=READ_ONLY,
                tags={"text-to-sql"},
            )
        )
        self.mcp.add_tool(
            Tool.from_function(
                fn=get_table_metadata,
                description=get_table_metadata.__doc__,
                title="Show table metadata",
                annotations=READ_ONLY,
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
                title="List documentation pages",
                annotations=READ_ONLY,
                tags={"documentation"},
            )
        )
        self.mcp.add_tool(
            Tool.from_function(
                fn=fetch_cratedb_docs,
                description=fetch_cratedb_docs.__doc__,
                title="Fetch documentation page",
                annotations=READ_ONLY_OPEN_WORLD,
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
                title="Show cluster health",
                annotations=READ_ONLY,
                tags={"health", "monitoring", "status"},
            )
        )

        return self
