import logging
import typing as t

import click
import fastmcp
from pueblo.util.cli import boot_click

from cratedb_mcp.core import CrateDbMcp
from cratedb_mcp.prompt import InstructionsPrompt
from cratedb_mcp.settings import InvalidSetting, Settings, check_positive_numbers

logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
@click.option(
    "--debug",
    envvar="CRATEDB_MCP_DEBUG",
    is_flag=True,
    default=False,
    help="Log at debug level, with the first 50 characters of each statement",
)
@click.pass_context
def cli(ctx: click.Context, debug: bool) -> None:
    """
    CrateDB MCP server.

    Documentation: https://github.com/crate/cratedb-mcp
    """

    # Tame logging of HTTPX to not reveal credentials.
    # https://github.com/encode/httpx/pull/3513#issuecomment-3360536080
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Set up logger.
    boot_click(ctx=ctx, debug=debug)


transport_types = t.Literal["stdio", "sse", "http", "streamable-http"]
transport_choices = t.get_args(transport_types)


def turn_off_update_check() -> None:
    """
    Start without FastMCP's request to PyPI for a newer FastMCP release,
    unless `FASTMCP_CHECK_FOR_UPDATES` is set.
    """
    if "check_for_updates" not in fastmcp.settings.model_fields_set:
        fastmcp.settings.check_for_updates = "off"


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
@click.option(
    "--instructions",
    envvar="CRATEDB_MCP_INSTRUCTIONS",
    type=str,
    required=False,
    help="If you want to change the default instructions prompt, use this option",
)
@click.option(
    "--conventions",
    envvar="CRATEDB_MCP_CONVENTIONS",
    type=str,
    required=False,
    help="If you want to add custom conventions to the prompt, use this option",
)
@click.pass_context
def serve(
    ctx: click.Context,
    transport: str,
    host: str,
    port: int,
    path: t.Optional[str],
    instructions: t.Optional[str],
    conventions: t.Optional[str],
) -> None:
    """
    Start MCP server.
    """
    try:
        Settings.cluster_url()
        check_positive_numbers()
    except InvalidSetting as e:
        raise click.UsageError(str(e)) from None
    logger.info(f"CrateDB MCP server starting with transport: {transport}")
    transport_kwargs = {}
    if transport in {"sse", "http", "streamable-http"}:
        transport_kwargs = {
            "host": host,
            "port": port,
            "path": path,
        }
    turn_off_update_check()
    mcp_cratedb = CrateDbMcp(instructions=instructions, conventions=conventions)
    mcp_cratedb.mcp.run(transport=t.cast(transport_types, transport), **transport_kwargs)  # type: ignore[arg-type]


@cli.command()
def show_prompt() -> None:
    """
    Display the system prompt.
    """
    print(InstructionsPrompt().render())  # noqa: T201
