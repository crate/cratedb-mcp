from typing import Optional

from fastmcp import FastMCP
from fastmcp.server.auth import TokenVerifier
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

# Tools running read-only statements towards the database, so clients may auto-approve them.
QUERY_TOOL = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
# When all statements are permitted, `query_sql` can modify and destroy data,
# so it must not be announced as read-only, otherwise clients may auto-approve writes.
QUERY_TOOL_WRITABLE = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=False
)
# Acquiring documentation resources touches the network, hence `openWorldHint`.
DOCS_TOOL = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=True)


class CrateDbMcp:
    """
    Small wrapper around the FastMCP API to provide instructions prompt at runtime.
    """

    def __init__(
        self,
        mcp: Optional[FastMCP] = None,
        instructions: Optional[str] = None,
        conventions: Optional[str] = None,
        auth: Optional[TokenVerifier] = None,
    ) -> None:
        prompt = InstructionsPrompt(instructions=instructions, conventions=conventions)
        self.mcp = mcp or FastMCP(
            name=__appname__,
            version=__version__,
            instructions=prompt.render(),
            auth=auth,
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
                annotations=(
                    QUERY_TOOL_WRITABLE if Settings.permit_all_statements() else QUERY_TOOL
                ),
            )
        )
        self.mcp.add_tool(
            Tool.from_function(
                fn=get_table_columns,
                description=get_table_columns.__doc__,
                tags={"text-to-sql"},
                annotations=QUERY_TOOL,
            )
        )
        self.mcp.add_tool(
            Tool.from_function(
                fn=get_table_metadata,
                description=get_table_metadata.__doc__,
                tags={"text-to-sql"},
                annotations=QUERY_TOOL,
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
                annotations=DOCS_TOOL,
            )
        )
        self.mcp.add_tool(
            Tool.from_function(
                fn=fetch_cratedb_docs,
                description=fetch_cratedb_docs.__doc__,
                tags={"documentation"},
                annotations=DOCS_TOOL,
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
                annotations=QUERY_TOOL,
            )
        )

        return self
