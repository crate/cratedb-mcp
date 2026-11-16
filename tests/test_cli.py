import os
import runpy
import sys
from unittest import mock

import fastmcp.server.server
import pytest
from click.testing import CliRunner

from cratedb_mcp import __version__
from cratedb_mcp.cli import cli
from cratedb_mcp.prompt import InstructionsPrompt


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

    # Invoke the program.
    runner = CliRunner()
    runner.invoke(
        cli,
        args=["serve", "--transport=http", "--port=65535"],
        catch_exceptions=False,
    )

    # Verify the outcome.
    assert run_mock.call_count == 1
    assert run_mock.call_args in [
        mock.call("http", host="127.0.0.1", port=65535, path=None),
        mock.call("http", show_banner=mock.ANY, host="127.0.0.1", port=65535, path=None),
    ]


def update_check_after_serve(mocker, configured=None):
    mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")
    mocker.patch.dict(os.environ)
    os.environ.pop("FASTMCP_CHECK_FOR_UPDATES", None)
    if configured:
        os.environ["FASTMCP_CHECK_FOR_UPDATES"] = configured
    settings = type(fastmcp.settings)()
    mocker.patch.object(fastmcp, "settings", settings)
    CliRunner().invoke(cli, args="serve", catch_exceptions=False)
    return settings.check_for_updates


def test_cli_starts_without_fastmcp_update_check(mocker):
    assert update_check_after_serve(mocker) == "off"


def test_cli_keeps_a_configured_fastmcp_update_check(mocker):
    assert update_check_after_serve(mocker, configured="stable") == "stable"


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
    assert capsys.readouterr().out.strip() == InstructionsPrompt().render()


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
