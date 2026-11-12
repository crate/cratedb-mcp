import asyncio
import os

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
    assert len(tools) == 8
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
