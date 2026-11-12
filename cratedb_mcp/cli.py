import logging
import os
import typing as t

import click
from pueblo.util.cli import boot_click

from cratedb_mcp.auth import BearerTokenVerifier
from cratedb_mcp.core import CrateDbMcp
from cratedb_mcp.prompt import InstructionsPrompt

logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """
    CrateDB MCP server.

    Documentation: https://github.com/crate/cratedb-mcp
    """

    # Tame logging of HTTPX to not reveal credentials.
    # https://github.com/encode/httpx/pull/3513#issuecomment-3360536080
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # Set up logger.
    boot_click(ctx=ctx)


transport_types = t.Literal["stdio", "sse", "http", "streamable-http"]
transport_choices = t.get_args(transport_types)


def http_security_options(
    allowed_hosts: t.Sequence[str], allowed_origins: t.Sequence[str]
) -> t.Dict[str, t.Any]:
    """
    Validate the Host and Origin headers of every HTTP request.

    Requests to a host outside `allowed_hosts` and the loopback names get 421,
    requests from a browser origin outside `allowed_origins` get 403.
    """
    return {
        "host_origin_protection": True,
        "allowed_hosts": list(allowed_hosts) or None,
        "allowed_origins": list(allowed_origins) or None,
    }


def http_auth(auth_disabled: bool) -> t.Optional[BearerTokenVerifier]:
    """
    Require the bearer token from `CRATEDB_MCP_AUTH_TOKEN` on HTTP requests.
    """
    if auth_disabled:
        logger.warning(
            "Authentication is disabled. Anyone who can reach the server can query the database."
        )
        return None
    token = os.getenv("CRATEDB_MCP_AUTH_TOKEN")
    if not token:
        raise click.UsageError(
            "Serving over HTTP requires a bearer token. Set CRATEDB_MCP_AUTH_TOKEN, "
            "or set CRATEDB_MCP_AUTH_DISABLED=true for local work."
        )
    if token != token.strip():
        raise click.UsageError(
            "CRATEDB_MCP_AUTH_TOKEN begins or ends with whitespace, such as a trailing "
            "newline, which clients do not send. Remove it."
        )
    return BearerTokenVerifier(token)


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
    "--allowed-host",
    "allowed_hosts",
    envvar="CRATEDB_MCP_ALLOWED_HOSTS",
    type=str,
    multiple=True,
    help="A host name clients may use to reach the server, besides localhost (for sse, http)",
)
@click.option(
    "--allowed-origin",
    "allowed_origins",
    envvar="CRATEDB_MCP_ALLOWED_ORIGINS",
    type=str,
    multiple=True,
    help="A browser origin permitted to call the server (for sse, http)",
)
@click.option(
    "--auth-disabled",
    envvar="CRATEDB_MCP_AUTH_DISABLED",
    is_flag=True,
    default=False,
    help="Serve without a bearer token, for local work only (for sse, http)",
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
    allowed_hosts: t.Tuple[str, ...],
    allowed_origins: t.Tuple[str, ...],
    auth_disabled: bool,
    instructions: t.Optional[str],
    conventions: t.Optional[str],
) -> None:
    """
    Start MCP server.
    """
    logger.info(f"CrateDB MCP server starting with transport: {transport}")
    if transport == "sse":
        logger.warning(
            "The sse transport is deprecated, as it is in the MCP specification. "
            "Use the http transport instead."
        )
    transport_kwargs: t.Dict[str, t.Any] = {}
    auth = None
    if transport in {"sse", "http", "streamable-http"}:
        auth = http_auth(auth_disabled)
        transport_kwargs = {
            "host": host,
            "port": port,
            "path": path,
            **http_security_options(allowed_hosts, allowed_origins),
        }
    mcp_cratedb = CrateDbMcp(instructions=instructions, conventions=conventions, auth=auth)
    mcp_cratedb.mcp.run(transport=t.cast(transport_types, transport), **transport_kwargs)  # type: ignore[arg-type]


@cli.command()
def show_prompt() -> None:
    """
    Display the system prompt.
    """
    print(InstructionsPrompt().render())  # noqa: T201
