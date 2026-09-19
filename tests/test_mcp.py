import asyncio

import pytest
from fastmcp import Client

from cratedb_mcp.core import CrateDbMcp
from cratedb_mcp.tool import (
    fetch_cratedb_docs,
    get_cluster_health,
    get_cratedb_documentation_index,
    get_table_columns,
    get_table_metadata,
    query_sql,
)


def test_get_documentation_index():
    assert len(get_cratedb_documentation_index()) >= 3


def test_fetch_docs_forbidden():
    with pytest.raises(ValueError) as ex:
        fetch_cratedb_docs("https://example.com")
    assert ex.match("Link is not permitted: https://example.com")


def test_fetch_docs_permitted_github():
    response = fetch_cratedb_docs(
        "https://raw.githubusercontent.com/crate/crate/refs/heads/5.10/docs/general/builtins/scalar-functions.rst"
    )
    assert "initcap" in response


def test_fetch_docs_permitted_cratedb_com():
    response = fetch_cratedb_docs(
        "https://cratedb.com/docs/crate/reference/en/latest/_sources/general/builtins/scalar-functions.rst.txt"
    )
    assert "initcap" in response


def test_query_sql_permitted():
    assert query_sql("SELECT 42")["rows"] == [[42]]


def test_query_sql_forbidden_easy():
    with pytest.raises(PermissionError) as ex:
        assert "RelationUnknown" in str(
            query_sql("INSERT INTO foobar (id) VALUES (42) RETURNING id")
        )
    assert ex.match("Only read-only statements")


def test_query_sql_forbidden_sneak_value():
    with pytest.raises(PermissionError) as ex:
        query_sql("INSERT INTO foobar (operation) VALUES ('select')")
    assert ex.match("Only read-only statements")


def test_get_table_columns():
    response = str(get_table_columns())
    assert "information_schema" in response
    assert "pg_catalog" in response

    # Verify the returned structure.
    result = get_table_columns()
    assert isinstance(result, dict)
    expected_keys = {"user", "information_schema", "pg_catalog", "sys"}
    assert set(result.keys()) == expected_keys


def test_get_table_metadata():
    assert "partitions_health" in str(get_table_metadata())


def test_get_cluster_health():
    assert "missing_shards" in str(get_cluster_health())


def test_tool_annotations_permit_all(mocker):
    """
    Verify `query_sql` is not announced as read-only when all statements are permitted.
    """
    mocker.patch.dict("os.environ", {"CRATEDB_MCP_PERMIT_ALL_STATEMENTS": "true"})

    async def list_tools():
        async with Client(CrateDbMcp().mcp) as client:
            return await client.list_tools()

    with pytest.warns(UserWarning, match="All types of SQL statements are permitted"):
        tools = {tool.name: tool for tool in asyncio.run(list_tools())}
    annotations = tools["query_sql"].annotations
    assert annotations.readOnlyHint is False
    assert annotations.destructiveHint is True
    assert annotations.idempotentHint is False
    # Tools running fixed queries stay read-only.
    assert tools["get_table_columns"].annotations.readOnlyHint is True
    assert tools["get_cluster_health"].annotations.readOnlyHint is True


def test_tool_annotations():
    """
    Verify all tools are announced as read-only, so clients may auto-approve them.
    """

    async def list_tools():
        async with Client(CrateDbMcp().mcp) as client:
            return await client.list_tools()

    tools = asyncio.run(list_tools())
    assert len(tools) == 6
    for tool in tools:
        assert tool.annotations is not None, tool.name
        assert tool.annotations.readOnlyHint is True, tool.name
        assert tool.description, tool.name

    # Only the documentation tools talk to a remote service.
    open_world = {tool.name: tool.annotations.openWorldHint for tool in tools}
    assert open_world == {
        "query_sql": False,
        "get_table_columns": False,
        "get_table_metadata": False,
        "get_cratedb_documentation_index": True,
        "fetch_cratedb_docs": True,
        "get_cluster_health": False,
    }


def test_tool_permission_error_is_tool_error():
    """
    Verify denied statements are reported as tool execution errors, not protocol errors.
    """

    async def call_tool():
        async with Client(CrateDbMcp().mcp) as client:
            return await client.call_tool(
                "query_sql", {"query": "DROP TABLE foobar"}, raise_on_error=False
            )

    result = asyncio.run(call_tool())
    assert result.is_error is True
    assert "Only read-only statements" in str(result.content)
