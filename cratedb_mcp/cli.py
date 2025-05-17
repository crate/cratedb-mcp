import logging
import typing as t

import click
from pueblo.util.cli import boot_click

from cratedb_mcp.__main__ import mcp

logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """
    CrateDB MCP server.

    Documentation: https://github.com/crate/cratedb-mcp
    """
    boot_click(ctx=ctx)


transport_types = t.Literal["stdio", "sse", "streamable-http"]
transport_choices = t.get_args(transport_types)


@cli.command()
@click.option(
    "--transport",
    envvar="CRATEDB_MCP_TRANSPORT",
    type=click.Choice(transport_choices),
    default="stdio",
    help="The transport protocol (stdio, sse, streamable-http)",
)
@click.option(
    "--port",
    envvar="CRATEDB_MCP_PORT",
    type=int,
    default=8000,
    help="The port to listen on (for sse and streamable-http)",
)
@click.pass_context
def serve(ctx: click.Context, transport: str, port: int) -> None:
    """
    Start MCP server.
    """
    logger.info(f"CrateDB MCP server starting with transport: {transport}")
    mcp.settings.port = port
    mcp.run(transport=t.cast(transport_types, transport))
