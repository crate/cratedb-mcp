import asyncio
from unittest import mock

import fastmcp.server.server
import httpx
import pytest
from click.testing import CliRunner

from cratedb_mcp import __version__
from cratedb_mcp.cli import cli, make_auth, warn_insecure_cluster


def test_cli_version():
    """
    Verify `cratedb-mcp --version` works as expected.
    """

    # Invoke the program.
    runner = CliRunner()
    result = runner.invoke(
        cli,
        args="--version",
        catch_exceptions=False,
    )

    # Verify the outcome.
    assert result.exit_code == 0, result.output
    assert f"version {__version__}" in result.output


def test_cli_help():
    """
    Verify `cratedb-mcp --help` works as expected.
    """

    # Invoke the program.
    runner = CliRunner()
    result = runner.invoke(
        cli,
        args="--help",
        catch_exceptions=False,
    )

    # Verify the outcome.
    assert result.exit_code == 0, result.output
    assert "Start MCP server" in result.output
    assert "Display the system prompt" in result.output


def test_cli_show_prompt():
    """
    Verify `cratedb-mcp show-prompt` works as expected.
    """

    # Invoke the program.
    runner = CliRunner()
    result = runner.invoke(
        cli,
        args="show-prompt",
        catch_exceptions=False,
    )

    # Verify the outcome.
    assert result.exit_code == 0, result.output
    assert "Rules for writing SQL queries" in result.output
    assert "Tool instructions" in result.output


def test_cli_no_command_no_option():
    """
    Verify `cratedb-mcp` without subcommand displays help text but signals failure.
    """

    # Invoke the program.
    runner = CliRunner()
    result = runner.invoke(
        cli,
        catch_exceptions=False,
    )

    # Verify the outcome.
    assert result.exit_code == 2, result.output
    assert "Start MCP server" in result.output
    assert "Display the system prompt" in result.output


def test_cli_valid_default(mocker, capsys):
    """
    Verify `cratedb-mcp serve` works as expected.

    The test needs to mock `anyio.run`, otherwise the call would block forever.
    """
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")

    # Invoke the program.
    runner = CliRunner()
    runner.invoke(
        cli,
        args=["serve", "--no-check-cluster"],
        catch_exceptions=False,
    )

    # Verify the outcome.
    assert run_mock.call_count == 1
    assert run_mock.call_args in [
        mock.call("stdio"),
        mock.call("stdio", show_banner=mock.ANY),
    ]


def test_cli_valid_custom(mocker, capsys):
    """
    Verify `cratedb-mcp serve --transport=http --port=65535` works as expected.

    The test needs to mock `anyio.run`, otherwise the call would block forever.
    """
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")

    # Invoke the program.
    runner = CliRunner()
    runner.invoke(
        cli,
        args=["serve", "--transport=http", "--port=65535", "--no-check-cluster"],
        catch_exceptions=False,
    )

    # Verify the outcome.
    assert run_mock.call_count == 1
    assert run_mock.call_args in [
        mock.call(
            "http",
            host="127.0.0.1",
            port=65535,
            path=None,
            host_origin_protection=True,
            allowed_hosts=None,
            allowed_origins=None,
        ),
        mock.call(
            "http",
            show_banner=mock.ANY,
            host="127.0.0.1",
            port=65535,
            path=None,
            host_origin_protection=True,
            allowed_hosts=None,
            allowed_origins=None,
        ),
    ]


def test_cli_http_allowed_hosts_origins(mocker):
    """
    Verify additional hosts and origins are handed over to the HTTP transport guard.
    """
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")

    runner = CliRunner()
    runner.invoke(
        cli,
        args=[
            "serve",
            "--transport=http",
            "--allowed-host=example.com",
            "--allowed-origin=https://example.com",
            "--no-check-cluster",
        ],
        catch_exceptions=False,
    )

    assert run_mock.call_args.kwargs["host_origin_protection"] is True
    assert run_mock.call_args.kwargs["allowed_hosts"] == ["example.com"]
    assert run_mock.call_args.kwargs["allowed_origins"] == ["https://example.com"]


def test_cli_http_unauthenticated_rejected(mocker):
    """
    Verify the server refuses to listen on a non-loopback address without authentication.
    """
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        args=["serve", "--transport=http", "--host=0.0.0.0", "--no-check-cluster"],
        catch_exceptions=False,
    )

    assert result.exit_code == 2, result.output
    assert "Refusing to serve on `0.0.0.0` without authentication" in result.output
    assert run_mock.call_count == 0


def test_cli_http_unauthenticated_permitted(mocker):
    """
    Verify listening without authentication requires an explicit override.
    """
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")

    runner = CliRunner()
    runner.invoke(
        cli,
        args=[
            "serve",
            "--transport=http",
            "--host=0.0.0.0",
            "--allow-unauthenticated",
            "--no-check-cluster",
        ],
        catch_exceptions=False,
    )

    assert run_mock.call_count == 1
    assert run_mock.call_args.kwargs["host"] == "0.0.0.0"  # noqa: S104


def test_cli_http_authenticated(mocker):
    """
    Verify the server may listen on a non-loopback address when a bearer token is configured.
    """
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")

    runner = CliRunner()
    runner.invoke(
        cli,
        args=[
            "serve",
            "--transport=http",
            "--host=0.0.0.0",
            "--auth-token=s3cret",
            "--no-check-cluster",
        ],
        catch_exceptions=False,
    )

    assert run_mock.call_count == 1
    assert run_mock.call_args.kwargs["host"] == "0.0.0.0"  # noqa: S104


def test_cli_check_cluster_unavailable(mocker, caplog):
    """
    Verify an unreachable cluster is reported, without preventing startup.
    """
    mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")
    mocker.patch("cratedb_mcp.cli.get_cluster_version", side_effect=httpx.ConnectError("boom"))

    runner = CliRunner()
    runner.invoke(cli, args=["serve"], catch_exceptions=False)

    assert "Cannot connect to CrateDB at" in caplog.text


@pytest.mark.parametrize("url", ["http://secret@example.org:abc", "http://[::1"])
def test_cli_check_cluster_invalid_url(mocker, caplog, url):
    """
    Verify an invalid cluster URL is reported, without preventing startup or leaking credentials.
    """
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")
    mocker.patch.dict("os.environ", {"CRATEDB_CLUSTER_URL": url})

    runner = CliRunner()
    runner.invoke(cli, args=["serve"], catch_exceptions=False)

    assert "`CRATEDB_CLUSTER_URL` is invalid" in caplog.text
    assert "secret" not in caplog.text
    assert run_mock.call_count == 1


def test_cli_check_cluster_available(mocker, caplog):
    """
    Verify connectivity to the cluster is reported on startup.
    """
    mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")
    mocker.patch("cratedb_mcp.cli.get_cluster_version", return_value="6.2.0")

    runner = CliRunner()
    runner.invoke(cli, args=["serve"], catch_exceptions=False)

    assert "Connected to CrateDB 6.2.0 at" in caplog.text


def test_cli_invalid_transport_option(mocker, capsys):
    """
    Verify `cratedb-mcp serve` fails when an invalid transport is specified.
    """

    # Invoke the program.
    runner = CliRunner()
    result = runner.invoke(
        cli,
        args=["serve", "--transport", "foo"],
        catch_exceptions=False,
    )

    # Verify the outcome.
    assert result.exit_code == 2, result.output
    assert "Error: Invalid value for '--transport'" in result.output


def test_cli_invalid_transport_env(mocker, capsys):
    """
    Verify `cratedb-mcp serve` fails when an invalid transport is specified.
    """

    # Invoke the program.
    runner = CliRunner()
    result = runner.invoke(
        cli,
        args="serve",
        env={"CRATEDB_MCP_TRANSPORT": "foo"},
        catch_exceptions=False,
    )

    # Verify the outcome.
    assert result.exit_code == 2, result.output
    assert "Error: Invalid value for '--transport'" in result.output


def test_cli_invalid_port_option(mocker, capsys):
    """
    Verify `cratedb-mcp serve` fails when an invalid port is specified.
    """

    # Invoke the program.
    runner = CliRunner()
    result = runner.invoke(
        cli,
        args=["serve", "--port", "foo"],
        catch_exceptions=False,
    )

    # Verify the outcome.
    assert result.exit_code == 2, result.output
    assert "Error: Invalid value for '--port': 'foo' is not a valid integer." in result.output


def test_cli_invalid_port_env(mocker, capsys):
    """
    Verify `cratedb-mcp serve` fails when an invalid port is specified.
    """

    # Invoke the program.
    runner = CliRunner()
    result = runner.invoke(
        cli,
        args="serve",
        env={"CRATEDB_MCP_PORT": "foo"},
        catch_exceptions=False,
    )

    # Verify the outcome.
    assert result.exit_code == 2, result.output
    assert "Error: Invalid value for '--port': 'foo' is not a valid integer." in result.output


def test_cli_auth_token_empty(mocker):
    """
    Verify an empty authentication token is rejected, instead of disabling authentication.
    """
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")

    runner = CliRunner()
    result = runner.invoke(cli, args=["serve", "--transport=http", "--auth-token= "])

    assert result.exit_code == 2
    assert "The authentication token must not be empty" in result.output
    assert run_mock.call_count == 0


def test_cli_auth_token_non_ascii():
    """
    Verify tokens are compared byte-wise, so non-ASCII tokens work on both sides.
    """
    verifier = make_auth("s3crét")
    assert asyncio.run(verifier.verify_token("s3crét")) is not None
    assert asyncio.run(verifier.verify_token("s3cret")) is None
    assert asyncio.run(verifier.verify_token("wröng")) is None


@pytest.mark.parametrize(
    "url, warns",
    [
        ("http://admin:s3cret@example.org:4200", True),
        ("https://admin:s3cret@example.org:4200", False),
        ("http://admin:s3cret@localhost:4200", False),
        ("http://example.org:4200", False),
        ("http://[::1", False),
    ],
)
def test_cli_insecure_cluster(mocker, caplog, url, warns):
    """
    Verify a warning is emitted when credentials travel to a remote cluster without encryption.
    """
    mocker.patch.dict("os.environ", {"CRATEDB_CLUSTER_URL": url})
    warn_insecure_cluster()
    assert ("without encryption" in caplog.text) is warns
    assert "s3cret" not in caplog.text


def test_cli_transport_security_from_environment(mocker):
    """
    Verify deployments configured through the environment can announce hostnames and origins.
    """
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")
    mocker.patch.dict(
        "os.environ",
        {
            "CRATEDB_MCP_TRANSPORT": "http",
            "CRATEDB_MCP_HOST": "0.0.0.0",  # noqa: S104
            "CRATEDB_MCP_AUTH_TOKEN": "s3cret",
            "CRATEDB_MCP_ALLOWED_HOSTS": "cratedb-mcp mcp.example.com",
            "CRATEDB_MCP_ALLOWED_ORIGINS": "https://mcp.example.com",
        },
    )

    runner = CliRunner()
    result = runner.invoke(cli, args=["serve", "--no-check-cluster"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    assert run_mock.call_args.kwargs["allowed_hosts"] == ["cratedb-mcp", "mcp.example.com"]
    assert run_mock.call_args.kwargs["allowed_origins"] == ["https://mcp.example.com"]


def test_cli_allow_unauthenticated_from_environment(mocker):
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")
    mocker.patch.dict(
        "os.environ",
        {
            "CRATEDB_MCP_TRANSPORT": "http",
            "CRATEDB_MCP_HOST": "0.0.0.0",  # noqa: S104
            "CRATEDB_MCP_ALLOW_UNAUTHENTICATED": "true",
        },
    )

    runner = CliRunner()
    result = runner.invoke(cli, args=["serve", "--no-check-cluster"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    assert run_mock.call_count == 1


def test_cli_transport_sse_not_offered():
    """
    Verify the deprecated SSE transport is rejected, it lacks `Host`/`Origin` validation.
    """
    runner = CliRunner()
    result = runner.invoke(cli, args=["serve", "--transport=sse"])
    assert result.exit_code == 2
    assert "'sse' is not one of" in result.output
    assert "sse" not in runner.invoke(cli, args=["serve", "--help"]).output
