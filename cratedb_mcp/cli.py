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


transport_types = t.Literal["stdio", "sse", "http", "streamable-http"]
transport_choices = t.get_args(transport_types)


@cli.command()
@click.option(
    "--transport",
    envvar="CRATEDB_MCP_TRANSPORT",
    type=click.Choice(transport_choices),
    default="stdio",
    help="The transport protocol (stdio, sse, http, ex. streamable-http)",
)
@click.option(
    "--host",
    envvar="CRATEDB_MCP_HOST",
    type=str,
    default="127.0.0.1",
    help="The host to listen on (for sse, http)",
)
@click.option(
    "--port",
    envvar="CRATEDB_MCP_PORT",
    type=int,
    default=8000,
    help="The port to listen on (for sse, http)",
)
@click.option(
    "--path",
    envvar="CRATEDB_MCP_PATH",
    type=str,
    required=False,
    help="The URL path to serve on (for sse, http)",
)
@click.pass_context
def serve(
    ctx: click.Context, transport: str, host: str, port: int, path: t.Optional[str] = None
) -> None:
    """
    Start MCP server.
    """
    logger.info(f"CrateDB MCP server starting with transport: {transport}")
    transport_kwargs = {}
    if transport in {"sse", "http", "streamable-http"}:
        transport_kwargs = {
            "host": host,
            "port": port,
            "path": path,
        }
    mcp.run(transport=t.cast(transport_types, transport), **transport_kwargs)  # type: ignore[arg-type]
