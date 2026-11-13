import os

import pytest

from cratedb_mcp.settings import Settings


def test_settings_http_timeout_default():
    assert Settings.http_timeout() == 30.0


def test_settings_http_timeout_env_valid(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_HTTP_TIMEOUT": "42.42"})
    assert Settings.http_timeout() == 42.42


def test_settings_http_timeout_env_invalid(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_HTTP_TIMEOUT": "foo"})
    with pytest.warns(UserWarning) as record:
        assert Settings.http_timeout() == 30.0
    assert "Environment variable `CRATEDB_MCP_HTTP_TIMEOUT` invalid" in record[0].message.args[0]


def test_settings_max_rows_env_invalid(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_ROWS": "many"})
    with pytest.warns(UserWarning) as record:
        assert Settings.max_rows() == 100
    assert "Environment variable `CRATEDB_MCP_MAX_ROWS` invalid" in record[0].message.args[0]


def test_settings_max_chars_env_invalid(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": "lots"})
    with pytest.warns(UserWarning) as record:
        assert Settings.max_chars() == 50_000
    assert "Environment variable `CRATEDB_MCP_MAX_CHARS` invalid" in record[0].message.args[0]
