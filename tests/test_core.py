import asyncio
import os

import jsonschema
import pytest
from fastmcp import Client

from cratedb_mcp.core import CrateDbMcp


def tool_hints():
    async def fetch():
        async with Client(CrateDbMcp().mcp) as client:
            return await client.list_tools()

    return {
        tool.name: (tool.title, tool.annotations.model_dump(by_alias=True, exclude_none=True))
        for tool in asyncio.run(fetch())
    }


def test_tools_declare_title_and_read_only_hints():
    tools = tool_hints()
    assert len(tools) == 6
    for name, (title, hints) in tools.items():
        assert title, name
        assert hints["readOnlyHint"] is True, name
        assert hints["destructiveHint"] is False, name
        assert hints["idempotentHint"] is True, name
        assert hints["openWorldHint"] is (name == "fetch_cratedb_docs"), name


def test_query_sql_hints_follow_permit_all_statements(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_PERMIT_ALL_STATEMENTS": "true"})
    with pytest.warns(UserWarning, match="All types of SQL statements are permitted"):
        _, hints = tool_hints()["query_sql"]
    assert hints["readOnlyHint"] is False
    assert hints["destructiveHint"] is True
    assert hints["idempotentHint"] is False


CALLS = {
    "query_sql": {"query": "SELECT x FROM generate_series(1, 3) AS t(x)"},
    "get_cratedb_documentation_index": {},
    "get_cluster_health": {},
}


CRATE_RESULT = {"cols", "rows", "rowcount", "duration"}
RESULT_FIELDS = {
    "query_sql": CRATE_RESULT | {"truncated", "rows_returned", "note"},
    "get_cratedb_documentation_index": {"result"},
    "get_cluster_health": CRATE_RESULT | {"truncated", "rows_returned", "note"},
    "fetch_cratedb_docs": {"result"},
}


def declared_fields(schema):
    return set(schema.get("properties", {}))


def test_tools_declare_named_result_fields():
    async def fetch():
        async with Client(CrateDbMcp().mcp) as client:
            return await client.list_tools()

    for tool in asyncio.run(fetch()):
        assert declared_fields(tool.output_schema) == RESULT_FIELDS.get(tool.name, set()), tool.name


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        *CALLS.items(),
        ("query_sql", {"query": "SELECT x FROM generate_series(1, 1500) AS t(x)"}),
    ],
)
def test_results_validate_against_declared_schema(name, arguments):
    async def call():
        async with Client(CrateDbMcp().mcp) as client:
            tool = next(tool for tool in await client.list_tools() if tool.name == name)
            result = await client.call_tool(name, arguments)
            return tool.output_schema, result.structured_content

    schema, content = asyncio.run(call())
    jsonschema.validate(content, schema)


def test_absent_result_fields_stay_out_of_the_answer():
    async def call():
        async with Client(CrateDbMcp().mcp) as client:
            result = await client.call_tool("query_sql", {"query": "SELECT 42"})
            return result.structured_content

    assert set(asyncio.run(call())) == CRATE_RESULT | {"truncated", "rows_returned"}
