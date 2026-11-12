import asyncio

import httpx
import pytest
from fastmcp import Client

from cratedb_mcp.core import CrateDbMcp
from cratedb_mcp.tool import (
    documentation_index,
    fetch_cratedb_docs,
    get_cluster_health,
    get_cratedb_documentation_index,
    query_cratedb,
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
    with pytest.raises(ValueError) as ex:
        fetch_cratedb_docs("https://example.com")
    assert ex.match("Link is not permitted: https://example.com")


def test_fetch_docs_permitted_github():
    response = fetch_cratedb_docs(
        "https://raw.githubusercontent.com/crate/crate/refs/heads/5.10/docs/general/builtins/scalar-functions.rst"
    )
    assert "initcap" in response


def test_fetch_docs_permitted_docs_cratedb_com():
    response = fetch_cratedb_docs(
        "https://docs.cratedb.com/projects/crate-reference/en/latest/_sources/general/builtins/scalar-functions.rst.txt"
    )
    assert "initcap" in response


def test_fetch_docs_missing_page():
    with pytest.raises(httpx.HTTPStatusError):
        fetch_cratedb_docs("https://docs.cratedb.com/projects/guide/_sources/does-not-exist.md.txt")


def test_fetch_docs_redirect_forbidden(mocker):
    response = httpx.Response(
        200, text="elsewhere", request=httpx.Request("GET", "https://example.com/")
    )
    mocker.patch.object(documentation_index.client, "get", return_value=response)
    with pytest.raises(ValueError) as ex:
        fetch_cratedb_docs("https://docs.cratedb.com/projects/guide/")
    assert ex.match("Link redirects to a location that is not permitted: https://example.com/")


def test_query_sql_permitted():
    assert query_sql("SELECT 42").rows == [[42]]


def test_query_sql_trailing_slash(mocker):
    """Verify that query_sql works correctly when HTTP_URL has a trailing slash."""
    mocker.patch("cratedb_mcp.tool.HTTP_URL", "http://localhost:4200/")
    assert query_sql("SELECT 42").rows == [[42]]


def test_query_sql_forbidden_easy():
    with pytest.raises(PermissionError) as ex:
        assert "RelationUnknown" in str(
            query_sql("INSERT INTO foobar (id) VALUES (42) RETURNING id")
        )
    assert ex.match("Only one SELECT, WITH, VALUES or SHOW statement")


def test_query_sql_forbidden_sneak_value():
    with pytest.raises(PermissionError) as ex:
        query_sql("INSERT INTO foobar (operation) VALUES ('select')")
    assert ex.match("Only one SELECT, WITH, VALUES or SHOW statement")


@pytest.mark.parametrize(
    "query",
    [
        "WITH foo AS (SELECT 42 AS x) SELECT x FROM foo",
        "VALUES (42)",
        "SHOW search_path",
        "EXPLAIN ANALYZE SELECT 42",
    ],
)
def test_query_sql_runs_read_statements(query):
    assert query_sql(query).error is None


@pytest.fixture(scope="module")
def probe():
    query_cratedb("DROP TABLE IF EXISTS testdrive_readonly.probe")
    query_cratedb("CREATE TABLE testdrive_readonly.probe (id INT)")
    query_cratedb("INSERT INTO testdrive_readonly.probe VALUES (1)")
    query_cratedb("REFRESH TABLE testdrive_readonly.probe")
    yield
    query_cratedb("DROP TABLE IF EXISTS testdrive_readonly.probe")


@pytest.mark.parametrize(
    "statement",
    [
        "DROP TABLE testdrive_readonly.probe",
        "UPDATE testdrive_readonly.probe SET id = 2",
        "INSERT INTO testdrive_readonly.probe VALUES (2)",
        "DELETE FROM testdrive_readonly.probe",
    ],
)
@pytest.mark.parametrize("text", ["SELECT 1; {}", r"SELECT 'a\'; {}; --'", r"SELECT 'a\'; {} --'"])
def test_crate_refuses_second_statement(probe, text, statement):
    result = query_cratedb(text.format(statement))
    assert "ParsingException" in result["error"]["message"]
    query_cratedb("REFRESH TABLE testdrive_readonly.probe")
    assert query_cratedb("SELECT id FROM testdrive_readonly.probe")["rows"] == [[1]]


@pytest.mark.parametrize(
    "text",
    [
        "SELECT * INTO testdrive_readonly.copy FROM testdrive_readonly.probe",
        "SELECT * FROM testdrive_readonly.probe INTO testdrive_readonly.copy",
    ],
)
def test_crate_refuses_select_into(probe, text):
    assert "ParsingException" in query_cratedb(text)["error"]["message"]
    assert (
        "RelationUnknown"
        in query_cratedb("SELECT 1 FROM testdrive_readonly.copy")["error"]["message"]
    )


def test_get_cluster_health():
    assert "missing_shards" in get_cluster_health().cols
