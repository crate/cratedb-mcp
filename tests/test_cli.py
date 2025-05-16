import os
import sys

import pytest
from mcp.server import FastMCP

from cratedb_mcp import __appname__, __version__
from cratedb_mcp.cli import main


def test_cli_version(mocker, capsys):
    """
    Verify `cratedb-mcp --version` works as expected.
    """
    mocker.patch.object(sys, "argv", ["cratedb-mcp", "--version"])
    main()
    out, err = capsys.readouterr()
    assert __appname__ in out
    assert __version__ in out


def test_cli_default(mocker, capsys):
    """
    Verify `cratedb-mcp` works as expected.
    """
    mocker.patch.object(sys, "argv", ["cratedb-mcp"])
    run_mock = mocker.patch.object(FastMCP, "run")
    main()
    assert run_mock.call_count == 1


def test_cli_invalid_transport(mocker, capsys):
    """
    Verify `cratedb-mcp` fails when an invalid transport is specified.
    """
    mocker.patch.object(sys, "argv", ["cratedb-mcp"])
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_TRANSPORT": "foo"})
    with pytest.raises(ValueError) as excinfo:
        main()
    assert excinfo.match("Unsupported transport: 'foo'. Please use one of 'stdio', 'sse'.")
