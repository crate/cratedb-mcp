from unittest import mock

import fastmcp.server.server
from click.testing import CliRunner

from cratedb_mcp import __version__
from cratedb_mcp.cli import cli


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
        mock.call("stdio", show_banner=True),
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
        mock.call("http", show_banner=True, host="127.0.0.1", port=65535, path=None),
    ]


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
