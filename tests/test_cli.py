import asyncio
import importlib.resources
import os
import runpy
import sys
from unittest import mock

import fastmcp.server.server
import httpx2
import pytest
from click.testing import CliRunner
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from starlette.testclient import TestClient

from cratedb_mcp import __version__
from cratedb_mcp.cli import cli

BUILTIN = (importlib.resources.files("cratedb_mcp.prompt") / "instructions.md").read_text().strip()


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
    assert result.output.strip() == BUILTIN


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
        args="serve",
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
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_AUTH_TOKEN": "secret"})

    # Invoke the program.
    runner = CliRunner()
    runner.invoke(
        cli,
        args=["serve", "--transport=http", "--port=65535"],
        catch_exceptions=False,
    )

    # Verify the outcome.
    assert run_mock.call_count == 1
    options = {
        "host_origin_protection": True,
        "allowed_hosts": None,
        "allowed_origins": None,
    }
    assert run_mock.call_args in [
        mock.call("http", host="127.0.0.1", port=65535, path=None, **options),
        mock.call("http", show_banner=mock.ANY, host="127.0.0.1", port=65535, path=None, **options),
    ]


def test_cli_allowed_hosts_env(mocker, capsys):
    """
    Verify `CRATEDB_MCP_ALLOWED_HOSTS` reaches the Host check, one name per word.
    """
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")
    mocker.patch.dict(
        os.environ,
        {
            "CRATEDB_MCP_ALLOWED_HOSTS": "mcp.example.org mcp.internal:8000",
            "CRATEDB_MCP_AUTH_DISABLED": "true",
        },
    )

    runner = CliRunner()
    runner.invoke(cli, args=["serve", "--transport=http"], catch_exceptions=False)

    assert run_mock.call_count == 1
    assert run_mock.call_args.kwargs["host_origin_protection"] is True
    assert run_mock.call_args.kwargs["allowed_hosts"] == ["mcp.example.org", "mcp.internal:8000"]


def test_cli_http_requires_the_configured_token(mocker):
    """
    Verify `cratedb-mcp serve --transport=http` answers only requests that carry the token
    from `CRATEDB_MCP_AUTH_TOKEN`.
    """
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async", autospec=True)
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_AUTH_TOKEN": "secret"})
    os.environ.pop("CRATEDB_MCP_AUTH_DISABLED", None)

    CliRunner().invoke(cli, args=["serve", "--transport=http"], catch_exceptions=False)

    server = run_mock.call_args.args[0]
    with TestClient(server.http_app(), base_url="http://127.0.0.1:8000") as client:
        assert client.post("/mcp", json={}).status_code == 401
        response = client.post("/mcp", headers={"Authorization": "Bearer secret"}, json={})
    assert response.status_code not in (401, 403)


def test_cli_http_refuses_to_start_without_token(mocker):
    """
    Verify `cratedb-mcp serve --transport=http` stops when no token is configured.
    """
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")
    mocker.patch.dict(os.environ, clear=False)
    os.environ.pop("CRATEDB_MCP_AUTH_TOKEN", None)
    os.environ.pop("CRATEDB_MCP_AUTH_DISABLED", None)

    runner = CliRunner()
    result = runner.invoke(cli, args=["serve", "--transport=http"])

    assert result.exit_code == 2
    assert "requires a bearer token" in result.output
    assert run_mock.call_count == 0


def run_as_module(mocker, *args):
    """Run `python -m cratedb_mcp` and return its exit code."""
    mocker.patch.object(sys, "argv", ["cratedb_mcp", *args])
    mocker.patch.dict(sys.modules)
    sys.modules.pop("cratedb_mcp.__main__", None)
    with pytest.raises(SystemExit) as ex:
        runpy.run_module("cratedb_mcp", run_name="__main__")
    return ex.value.code


def test_module_runs_the_cli_with_its_subcommands(mocker, capsys):
    """
    Verify `python -m cratedb_mcp show-prompt` prints what `cratedb-mcp show-prompt` prints.
    """
    assert run_as_module(mocker, "show-prompt") == 0
    assert capsys.readouterr().out.strip() == BUILTIN


@pytest.mark.parametrize(
    ("args", "debug_env", "shown"),
    [
        (["serve"], None, False),
        (["--debug", "serve"], None, True),
        (["serve"], "true", True),
        (["serve"], "false", False),
    ],
)
def test_log_shows_statement_text_only_with_debug(tmp_path, args, debug_env, shown):
    """
    Verify `python -m cratedb_mcp --debug serve` and `CRATEDB_MCP_DEBUG=true` log the
    start of each statement, and that no run logs the lines of the HTTP libraries.
    """
    env = dict(os.environ)
    env.pop("CRATEDB_MCP_DEBUG", None)
    env["FASTMCP_CHECK_FOR_UPDATES"] = "off"
    if debug_env is not None:
        env["CRATEDB_MCP_DEBUG"] = debug_env
    log = tmp_path / "server.log"
    server = StdioTransport(
        command=sys.executable,
        args=["-m", "cratedb_mcp", *args],
        env=env,
        keep_alive=False,
        log_file=log,
    )

    async def call():
        async with Client(server) as client:
            await client.call_tool("query_sql", {"query": "SELECT 'a5e1d'"}, raise_on_error=False)

    asyncio.run(call())
    text = log.read_text()
    assert ("Permitted SQL expression: SELECT 'a5e1d'" in text) is shown
    assert "[httpx" not in text
    assert "[httpcore" not in text


def test_cli_http_refuses_a_token_with_surrounding_whitespace(mocker):
    """
    Verify `cratedb-mcp serve --transport=http` stops when the token ends with a newline.
    """
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_AUTH_TOKEN": "secret\n"})
    os.environ.pop("CRATEDB_MCP_AUTH_DISABLED", None)

    runner = CliRunner()
    result = runner.invoke(cli, args=["serve", "--transport=http"])

    assert result.exit_code == 2
    assert "begins or ends with whitespace" in result.output
    assert run_mock.call_count == 0


def test_cli_http_auth_disabled(mocker):
    """
    Verify `--auth-disabled` starts the HTTP server without a token.
    """
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")
    mocker.patch.dict(os.environ, clear=False)
    os.environ.pop("CRATEDB_MCP_AUTH_TOKEN", None)

    runner = CliRunner()
    runner.invoke(
        cli, args=["serve", "--transport=http", "--auth-disabled"], catch_exceptions=False
    )

    assert run_mock.call_count == 1


def test_cli_marks_sse_deprecated(mocker, caplog):
    """
    Verify `cratedb-mcp serve` marks the sse transport as deprecated, in its help and at start.
    """
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")

    runner = CliRunner()
    runner.invoke(cli, args=["serve", "--transport=sse", "--auth-disabled"], catch_exceptions=False)

    assert run_mock.call_count == 1
    assert "The sse transport is deprecated" in caplog.text

    help_text = " ".join(runner.invoke(cli, args=["serve", "--help"]).output.split())
    assert "or the deprecated sse" in help_text
    assert "for sse" not in help_text


def test_serve_logs_no_request_line_of_httpx2(mocker, caplog):
    """
    Verify `cratedb-mcp serve` logs no request line of httpx2, the HTTP library through
    which FastMCP asks PyPI for a newer release at start.
    """
    mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")
    CliRunner().invoke(cli, args="serve", catch_exceptions=False)

    transport = httpx2.MockTransport(lambda request: httpx2.Response(200))
    with httpx2.Client(transport=transport) as client:
        client.get("https://pypi.org/pypi/fastmcp/json")

    assert "HTTP Request" not in caplog.text


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
