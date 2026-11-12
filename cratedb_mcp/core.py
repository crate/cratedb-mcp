from typing import Any, Optional

from fastmcp import FastMCP
from fastmcp.tools import FunctionTool, Tool, ToolResult
from mcp.types import TextContent, ToolAnnotations

from cratedb_mcp.prompt import InstructionsPrompt
from cratedb_mcp.settings import Settings

from . import __appname__, __version__
from .tool import (
    describe_table,
    explain_query,
    fetch_cratedb_docs,
    get_cluster_health,
    get_cratedb_documentation_index,
    list_schemas,
    list_tables,
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


class ListTool(FunctionTool):
    """A tool returning a list, whose empty list still reaches the model as the text `[]`."""

    def convert_result(self, raw_value: Any) -> ToolResult:
        result = super().convert_result(raw_value)
        if not result.content:
            result.content = [TextContent(type="text", text="[]")]
        return result


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
                fn=explain_query,
                description=explain_query.__doc__,
                title="Explain query",
                annotations=READ_ONLY,
                tags={"text-to-sql"},
            )
        )
        self.mcp.add_tool(
            ListTool.from_function(
                fn=list_schemas,
                description=list_schemas.__doc__,
                title="List schemas",
                annotations=READ_ONLY,
                tags={"text-to-sql"},
            )
        )
        self.mcp.add_tool(
            ListTool.from_function(
                fn=list_tables,
                description=list_tables.__doc__,
                title="List tables",
                annotations=READ_ONLY,
                tags={"text-to-sql"},
            )
        )
        self.mcp.add_tool(
            Tool.from_function(
                fn=describe_table,
                description=describe_table.__doc__,
                title="Describe table",
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
