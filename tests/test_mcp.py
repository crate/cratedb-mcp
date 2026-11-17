import asyncio

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
    assert ex.match("Only one SELECT, WITH, VALUES or SHOW statement")


def test_query_sql_forbidden_sneak_value():
    with pytest.raises(ToolError) as ex:
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
    assert query_sql(query).rows


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


def test_calls_to_crate_ask_for_an_uncompressed_answer(answer_with):
    sent = []

    def answer(request):
        sent.append(request.headers)
        return httpx.Response(200, json={"cols": [], "rows": [], "rowcount": 0})

    answer_with(answer)
    query_cratedb("SELECT 1")
    (headers,) = sent
    assert headers["Accept-Encoding"] == "identity"
