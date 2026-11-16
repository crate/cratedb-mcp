from typing import Optional

from fastmcp import FastMCP
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from fastmcp.tools import Tool, ToolResult
from mcp.types import CallToolRequestParams

from cratedb_mcp.prompt import InstructionsPrompt

from . import __appname__, __version__
from .tool import (
    calling_tool,
    fetch_cratedb_docs,
    get_cluster_health,
    get_cratedb_documentation_index,
    get_table_columns,
    get_table_metadata,
    query_sql,
)


class NameCallingTool(Middleware):
    """Name the tool in the log lines of the calls to CrateDB it makes."""

    async def on_call_tool(
        self,
        context: MiddlewareContext[CallToolRequestParams],
        call_next: CallNext[CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        token = calling_tool.set(context.message.name)
        try:
            return await call_next(context)
        finally:
            calling_tool.reset(token)


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
        self.mcp.add_middleware(NameCallingTool())

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
