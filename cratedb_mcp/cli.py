import logging
import secrets
import typing as t
from urllib.parse import urlsplit

import click
import httpx
from fastmcp.exceptions import ToolError
from fastmcp.server.auth.providers.debug import DebugTokenVerifier
from pueblo.util.cli import boot_click

from cratedb_mcp.core import CrateDbMcp
from cratedb_mcp.prompt import InstructionsPrompt
from cratedb_mcp.settings import Settings
from cratedb_mcp.tool import get_cluster_version

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


# NB: The deprecated `sse` transport is not offered, its FastMCP implementation
# lacks the `Host`/`Origin` validation enabled below.
transport_types = t.Literal["stdio", "http", "streamable-http"]
transport_choices = t.get_args(transport_types)
http_transports = {"http", "streamable-http"}
loopback_hosts = {"127.0.0.1", "::1", "localhost"}


def make_auth(token: str) -> DebugTokenVerifier:
    """
    Create a bearer token verifier for the MCP HTTP transport.

    FastMCP ships no dedicated verifier for shared secrets, this uses the
    generic token verifier with a constant-time comparison.
    """
    # Compare bytes, because `compare_digest` rejects non-ASCII text.
    expected = token.encode("utf-8")
    return DebugTokenVerifier(
        validate=lambda candidate: secrets.compare_digest(candidate.encode("utf-8"), expected)
    )


def warn_insecure_cluster() -> None:
    """
    Warn about submitting credentials to a remote CrateDB cluster without encryption.
    """
    try:
        parts = urlsplit(Settings.cluster_url())
    except ValueError:
        return
    if parts.scheme != "http" or parts.hostname in loopback_hosts:
        return
    if Settings.cluster_token() or Settings.cluster_auth():
        logger.warning(
            f"Credentials are sent to CrateDB at `{parts.hostname}` without encryption. "
            f"Please use an `https://` cluster URL."
        )


def verify_cluster() -> None:
    """
    Report connectivity to the configured CrateDB cluster, without failing the server.

    Failing fast on an unreachable cluster is not desirable, because the
    documentation tools keep working without a database connection.
    """
    try:
        url = Settings.cluster_url()
        # Use a short timeout, to not defer startup when the cluster does not respond.
        version = get_cluster_version(timeout=min(Settings.http_timeout(), 5.0))
    except (httpx.InvalidURL, ValueError) as e:
        # NB: Do not echo the URL here, it could not be sanitized from credentials.
        logger.warning(f"Cannot connect to CrateDB, `CRATEDB_CLUSTER_URL` is invalid: {e}")
        return
    except (ToolError, httpx.HTTPError) as e:
        logger.warning(f"Cannot connect to CrateDB at {url}: {e}")
        return
    logger.info(f"Connected to CrateDB {version} at {url}")


@cli.command()
@click.option(
    "--transport",
    envvar="CRATEDB_MCP_TRANSPORT",
    type=click.Choice(transport_choices),
    default="stdio",
    help="The transport protocol (stdio, http, ex. streamable-http)",
)
@click.option(
    "--host",
    envvar="CRATEDB_MCP_HOST",
    type=str,
    default="127.0.0.1",
    help="The host to listen on (for http)",
)
@click.option(
    "--port",
    envvar="CRATEDB_MCP_PORT",
    type=int,
    default=8000,
    help="The port to listen on (for http)",
)
@click.option(
    "--path",
    envvar="CRATEDB_MCP_PATH",
    type=str,
    required=False,
    help="The URL path to serve on (for http)",
)
@click.option(
    "--auth-token",
    envvar="CRATEDB_MCP_AUTH_TOKEN",
    type=str,
    required=False,
    help="The bearer token MCP clients must present (for http)",
)
@click.option(
    "--allow-unauthenticated",
    envvar="CRATEDB_MCP_ALLOW_UNAUTHENTICATED",
    is_flag=True,
    default=False,
    help="Permit listening on a non-loopback address without authentication. Not recommended",
)
@click.option(
    "--allowed-host",
    "allowed_hosts",
    envvar="CRATEDB_MCP_ALLOWED_HOSTS",
    multiple=True,
    type=str,
    help="Additional hostname permitted in the `Host` header, required when "
    "serving on a public hostname, which is otherwise rejected with HTTP 421 (for http). "
    "The environment variable accepts multiple values, separated by whitespace",
)
@click.option(
    "--allowed-origin",
    "allowed_origins",
    envvar="CRATEDB_MCP_ALLOWED_ORIGINS",
    multiple=True,
    type=str,
    help="Additional browser origin permitted in the `Origin` header (for http). "
    "The environment variable accepts multiple values, separated by whitespace",
)
@click.option(
    "--check-cluster/--no-check-cluster",
    default=True,
    help="Report connectivity to the CrateDB cluster on startup",
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
    auth_token: t.Optional[str],
    allow_unauthenticated: bool,
    allowed_hosts: t.Tuple[str, ...],
    allowed_origins: t.Tuple[str, ...],
    check_cluster: bool,
    instructions: t.Optional[str],
    conventions: t.Optional[str],
) -> None:
    """
    Start MCP server.
    """
    logger.info(f"CrateDB MCP server starting with transport: {transport}")

    # An empty token must not silently disable authentication.
    if auth_token is not None and not auth_token.strip():
        raise click.UsageError("The authentication token must not be empty.")

    transport_kwargs = {}
    if transport in http_transports:
        if not auth_token and host not in loopback_hosts and not allow_unauthenticated:
            raise click.UsageError(
                f"Refusing to serve on `{host}` without authentication. "
                f"Please use `--auth-token`, or `--allow-unauthenticated` to override."
            )
        transport_kwargs = {
            "host": host,
            "port": port,
            "path": path,
            # Protect against DNS rebinding attacks, per MCP transport security guidance.
            "host_origin_protection": True,
            "allowed_hosts": list(allowed_hosts) or None,
            "allowed_origins": list(allowed_origins) or None,
        }

    warn_insecure_cluster()
    if check_cluster:
        verify_cluster()

    mcp_cratedb = CrateDbMcp(
        instructions=instructions,
        conventions=conventions,
        auth=make_auth(auth_token) if auth_token else None,
    )
    mcp_cratedb.mcp.run(transport=t.cast(transport_types, transport), **transport_kwargs)  # type: ignore[arg-type]


@cli.command()
def show_prompt() -> None:
    """
    Display the system prompt.
    """
    print(InstructionsPrompt().render())  # noqa: T201
