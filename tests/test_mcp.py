import asyncio
import logging
import re

import httpx
import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from cratedb_mcp.core import CrateDbMcp
from cratedb_mcp.settings import Settings
from cratedb_mcp.tool import (
    fetch_cratedb_docs,
    get_cluster_health,
    get_cratedb_documentation_index,
    get_table_columns,
    get_table_metadata,
    query_sql,
)


def test_server_speaks_protocol_2026_07_28():
    async def negotiate():
        async with Client(CrateDbMcp().mcp) as client:
            return client.protocol_version

    assert asyncio.run(negotiate()) == "2026-07-28"


def test_get_documentation_index():
    assert len(get_cratedb_documentation_index()) >= 3


def test_fetch_docs_forbidden():
    with pytest.raises(ToolError) as ex:
        fetch_cratedb_docs("https://example.com")
    assert ex.match("Link is not permitted: https://example.com")


def test_fetch_docs_permitted_github_index_link(docs_site):
    response = fetch_cratedb_docs(
        "https://raw.githubusercontent.com/crate/crate/refs/heads/master/README.rst"
    )
    assert "initcap" in response


def test_fetch_docs_permitted_docs_cratedb_com(docs_site):
    response = fetch_cratedb_docs(
        "https://docs.cratedb.com/projects/crate-reference/en/latest/_sources/general/builtins/scalar-functions.rst.txt"
    )
    assert "initcap" in response


def test_fetch_docs_missing_page(docs_site):
    link = "https://docs.cratedb.com/projects/guide/_sources/does-not-exist.md.txt"
    docs_site.pages[link] = lambda: httpx.Response(404)
    with pytest.raises(ToolError) as ex:
        fetch_cratedb_docs(link)
    assert str(ex.value) == "The page answered HTTP 404."


def test_query_sql_permitted():
    assert query_sql("SELECT 42").rows == [[42]]


def test_query_sql_trailing_slash(mocker):
    """Verify that query_sql works correctly when the cluster address has a trailing slash."""
    cluster = Settings.cluster_url()
    address = cluster.copy_with(path=cluster.path.rstrip("/") + "/")
    mocker.patch.object(Settings, "cluster_url", return_value=address)
    assert query_sql("SELECT 42").rows == [[42]]


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
    assert "missing_shards" in get_cluster_health().cols


def test_log_names_tool_duration_and_rows_and_leaves_the_statement_to_debug(caplog):
    async def run():
        async with Client(CrateDbMcp().mcp) as client:
            await client.call_tool("query_sql", {"query": "SELECT 'marker-7f3a'"})
            await client.call_tool(
                "query_sql", {"query": "SELECT * FROM doc.missing_7f3a"}, raise_on_error=False
            )

    caplog.set_level(logging.INFO)
    asyncio.run(run())
    assert "7f3a" not in caplog.text
    lines = [record.getMessage() for record in caplog.records if record.name == "cratedb_mcp.tool"]
    assert len(lines) == 2
    assert re.fullmatch(r"query_sql: CrateDB call took \d+ ms, 1 rows", lines[0])
    assert re.fullmatch(r"query_sql: CrateDB call failed after \d+ ms", lines[1])
