import asyncio
import logging
import os

import fastmcp.server.server
import pytest
from click.testing import CliRunner
from fastmcp import Client

from cratedb_mcp.cli import cli
from cratedb_mcp.core import CrateDbMcp
from cratedb_mcp.settings import Settings

OUTSIDE = "it holds an @ outside the user name and password"
BROKEN_ADDRESSES = {
    "slash": ("http://mcp:Qx7m/Pz9w@crate.example:4200", "its port is not a number"),
    "hash": ("http://mcp:Qx7m#Pz9w@crate.example:4200", "its port is not a number"),
    "question-mark": ("http://mcp:Qx7m?Pz9w@crate.example:4200", "its port is not a number"),
    "digits-before-slash": ("http://mcp:4711/Pz9w@crate.example:4200", OUTSIDE),
    "digits-before-hash": ("http://mcp:4711#Pz9w@crate.example:4200", OUTSIDE),
    "line-break": ("http://mcp:Qx7m\nPz9w@crate.example:4200", "it is not a valid URL"),
}


@pytest.fixture
def cluster_url(mocker):
    def use(address):
        mocker.patch.dict(os.environ, {"CRATEDB_CLUSTER_URL": address})
        Settings.cluster_url.cache_clear()

    yield use
    Settings.cluster_url.cache_clear()


def fragments(address):
    password = address.split("mcp:", 1)[1].split("@", 1)[0]
    return {
        password[start:end]
        for start in range(len(password))
        for end in range(start + 4, len(password) + 1)
    }


@pytest.mark.parametrize(
    ("address", "fault"), list(BROKEN_ADDRESSES.values()), ids=list(BROKEN_ADDRESSES)
)
def test_broken_cluster_address_stops_the_start_without_showing_any_of_it(
    mocker, cluster_url, address, fault
):
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")
    cluster_url(address)
    result = CliRunner().invoke(cli, args="serve")
    assert result.exit_code == 2
    assert f"CRATEDB_CLUSTER_URL cannot be used, because {fault}" in result.output
    assert "must be percent-encoded" in result.output
    assert not [part for part in fragments(address) if part in result.output]
    assert run_mock.call_count == 0


@pytest.mark.parametrize(
    ("address", "fault"), list(BROKEN_ADDRESSES.values()), ids=list(BROKEN_ADDRESSES)
)
def test_broken_cluster_address_stays_out_of_tool_errors_and_log(
    caplog, cluster_url, address, fault
):
    async def call():
        async with Client(CrateDbMcp().mcp) as client:
            return await client.call_tool("query_sql", {"query": "SELECT 1"}, raise_on_error=False)

    cluster_url(address)
    caplog.set_level(logging.DEBUG)
    result = asyncio.run(call())
    text = " ".join(block.text for block in result.content)
    assert result.is_error is True
    assert fault in text
    assert not [part for part in fragments(address) if part in text + caplog.text]


@pytest.mark.parametrize(
    ("address", "fault"),
    [
        ("crate.example:4200", "it does not start with http:// or https://"),
        ("http://", "it names no host"),
        ("http://crate.example:70000", "its port is above 65535"),
        ("http://crate.example:4200/?pretty", "it holds a query (?) or a fragment (#)"),
    ],
)
def test_cluster_address_that_is_no_http_url_with_a_host_is_refused(cluster_url, address, fault):
    cluster_url(address)
    result = CliRunner().invoke(cli, args="serve")
    assert result.exit_code == 2
    assert f"CRATEDB_CLUSTER_URL cannot be used, because {fault}." in result.output


@pytest.mark.parametrize(
    ("name", "value", "fault"),
    [
        ("CRATEDB_MCP_MAX_ROWS", "0", "it is zero or negative"),
        ("CRATEDB_MCP_MAX_ROWS", "-5", "it is zero or negative"),
        ("CRATEDB_MCP_MAX_ROWS", "many", "it is not a whole number"),
        ("CRATEDB_MCP_MAX_CHARS", "0", "it is zero or negative"),
        ("CRATEDB_MCP_MAX_CHARS", "-5", "it is zero or negative"),
        ("CRATEDB_MCP_MAX_CHARS", "1.5", "it is not a whole number"),
        ("CRATEDB_MCP_HTTP_TIMEOUT", "0", "it is zero or negative"),
        ("CRATEDB_MCP_HTTP_TIMEOUT", "-5", "it is zero or negative"),
        ("CRATEDB_MCP_HTTP_TIMEOUT", "soon", "it is not a number"),
        ("CRATEDB_MCP_HTTP_TIMEOUT", "nan", "it is not a number"),
        ("CRATEDB_MCP_HTTP_TIMEOUT", "inf", "it is infinite"),
    ],
)
def test_limit_that_is_not_a_number_above_zero_stops_the_start(mocker, name, value, fault):
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")
    mocker.patch.dict(os.environ, {name: value})
    result = CliRunner().invoke(cli, args="serve")
    assert result.exit_code == 2
    assert f"{name} cannot be used, because {fault}." in result.output
    assert run_mock.call_count == 0


def test_limits_that_are_numbers_above_zero_let_the_server_start(mocker):
    run_mock = mocker.patch.object(fastmcp.server.server.FastMCP, "run_async")
    limits = {
        "CRATEDB_MCP_MAX_ROWS": "5",
        "CRATEDB_MCP_MAX_CHARS": "1000",
        "CRATEDB_MCP_HTTP_TIMEOUT": "0.5",
    }
    mocker.patch.dict(os.environ, limits)
    assert CliRunner().invoke(cli, args="serve").exit_code == 0
    assert run_mock.call_count == 1


@pytest.mark.parametrize("args", ["--help", "show-prompt"])
def test_help_and_prompt_work_with_broken_settings(mocker, cluster_url, args):
    cluster_url(BROKEN_ADDRESSES["slash"][0])
    limits = ("CRATEDB_MCP_MAX_ROWS", "CRATEDB_MCP_MAX_CHARS", "CRATEDB_MCP_HTTP_TIMEOUT")
    mocker.patch.dict(os.environ, dict.fromkeys(limits, "0"))
    assert CliRunner().invoke(cli, args=args).exit_code == 0


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
        assert Settings.max_rows() == 1000
    assert "Environment variable `CRATEDB_MCP_MAX_ROWS` invalid" in record[0].message.args[0]


def test_settings_max_chars_env_invalid(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": "lots"})
    with pytest.warns(UserWarning) as record:
        assert Settings.max_chars() == 50_000
    assert "Environment variable `CRATEDB_MCP_MAX_CHARS` invalid" in record[0].message.args[0]
