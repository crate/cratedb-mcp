import logging
import os
import typing as t

from cratedb_mcp.__main__ import mcp

logger = logging.getLogger(__name__)


def main():
    transport = os.getenv("CRATEDB_MCP_TRANSPORT", "stdio")
    if transport not in ("stdio", "sse"):
        raise ValueError(f"Unsupported transport: '{transport}'. Please use one of 'stdio', 'sse'.")
    logger.info(f"Starting CrateDB MCP server using transport '{transport}'")
    mcp.run(transport=t.cast(t.Literal["stdio", "sse"], transport))
