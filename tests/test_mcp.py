import asyncio
import json

import pytest
from fastmcp import Client
from fastmcp.client import FastMCPTransport
from fastmcp.exceptions import ToolError

from cratedb_mcp.__main__ import mcp

transport = FastMCPTransport(mcp)
client = Client(transport=transport)


async def query_sql_async(sql: str) -> dict:
    async with client:
        response = await client.call_tool("query_sql", {"query": sql})
        return json.loads(response[0].text)


def query_sql(sql: str) -> dict:
    return asyncio.run(query_sql_async(sql))


async def call_tool_async(name: str, args: dict = None, decode_json: bool = False):
    async with client:
        response = await client.call_tool(name, args)
        if decode_json:
            return json.loads(response[0].text)
        return response[0].text


def call_tool(name: str, args: dict = None, decode_json: bool = False):
    return asyncio.run(call_tool_async(name, args, decode_json))


def test_get_documentation_index():
    assert len(call_tool("get_cratedb_documentation_index", decode_json=True)) >= 3


def test_fetch_docs_forbidden():
    with pytest.raises(ToolError) as ex:
        call_tool("fetch_cratedb_docs", {"link": "https://example.com"})
    assert ex.match("Link is not permitted: https://example.com")


def test_fetch_docs_permitted_github():
    response = call_tool(
        "fetch_cratedb_docs",
        {
            "link": "https://raw.githubusercontent.com/crate/crate/refs/heads/5.10/docs/general/builtins/scalar-functions.rst"
        },
    )
    assert "initcap" in response


def test_fetch_docs_permitted_cratedb_com():
    response = call_tool(
        "fetch_cratedb_docs",
        {
            "link": "https://cratedb.com/docs/crate/reference/en/latest/_sources/general/builtins/scalar-functions.rst.txt"
        },
    )
    assert "initcap" in response


def test_query_sql_permitted():
    assert query_sql("SELECT 42")["rows"] == [[42]]


def test_query_sql_trailing_slash(mocker):
    """Verify that query_sql works correctly when HTTP_URL has a trailing slash."""
    mocker.patch("cratedb_mcp.__main__.HTTP_URL", "http://localhost:4200/")
    assert query_sql("SELECT 42")["rows"] == [[42]]


def test_query_sql_forbidden_easy():
    with pytest.raises(ToolError) as ex:
        assert "RelationUnknown" in str(
            query_sql("INSERT INTO foobar (id) VALUES (42) RETURNING id")
        )
    assert ex.match("Only queries that have a SELECT statement are allowed")


def test_query_sql_forbidden_sneak_value():
    with pytest.raises(ToolError) as ex:
        query_sql("INSERT INTO foobar (operation) VALUES ('select')")
    assert ex.match("Only queries that have a SELECT statement are allowed")


def test_get_table_metadata():
    assert "partitions_health" in str(call_tool("get_table_metadata"))


def test_get_health():
    result = call_tool("get_health")
    assert "missing_shards" in str(result)
