import os

import httpx
import pytest

from cratedb_mcp import tool
from cratedb_mcp.tool import (
    describe_table,
    get_cluster_health,
    list_schemas,
    list_tables,
    query_cratedb,
    query_sql,
)


def test_query_sql_cuts_rows_at_default_cap():
    result = query_sql("SELECT x FROM generate_series(1, 1500) AS t(x)")
    assert len(result.rows) == result.rows_returned == 1000
    assert result.truncated is True
    assert result.note == (
        "Only 1000 of 1500 rows are shown, because an answer holds at most 1000 of them. "
        "Narrow the query with a WHERE clause or an aggregation, or read the rows in parts "
        "with LIMIT and OFFSET in the query."
    )


@pytest.mark.parametrize(
    ("env", "limit"),
    [({}, 20), ({"CRATEDB_MCP_MAX_ROWS": "1200"}, 1100), ({}, 1000)],
    ids=["default-cap", "configured-cap", "equal-to-cap"],
)
def test_query_sql_cuts_at_a_limit_up_to_the_row_cap(mocker, env, limit):
    mocker.patch.dict(os.environ, env)
    result = query_sql("SELECT x FROM generate_series(1, 1500) AS t(x)", limit=limit)
    assert result.rows == [[x] for x in range(1, limit + 1)]
    assert result.rows_returned == limit
    assert result.truncated is True
    assert result.note == (
        f"Only {limit} of 1500 rows are shown, because `limit` asks for {limit} of them."
    )


@pytest.mark.parametrize(
    ("env", "cap"),
    [({}, 1000), ({"CRATEDB_MCP_MAX_ROWS": "1200"}, 1200)],
    ids=["default-cap", "configured-cap"],
)
def test_query_sql_limit_above_the_row_cap_gives_the_cap(mocker, env, cap):
    mocker.patch.dict(os.environ, env)
    result = query_sql("SELECT x FROM generate_series(1, 1500) AS t(x)", limit=5000)
    assert len(result.rows) == result.rows_returned == cap
    assert result.truncated is True
    assert result.note.startswith(
        f"Only {cap} of 1500 rows are shown, because an answer holds at most {cap} of them."
    )


def test_query_sql_small_result_is_complete():
    result = query_sql("SELECT x FROM generate_series(1, 3) AS t(x)")
    assert result.rows == [[1], [2], [3]]
    assert result.rows_returned == 3
    assert result.truncated is False
    assert result.note is None


@pytest.mark.parametrize(
    "query",
    [
        "SELECT repeat('x', 19), 1 FROM generate_series(1, 10)",
        "SELECT repeat('日', 19), 1 FROM generate_series(1, 10)",
    ],
    ids=["ascii", "non-ascii"],
)
def test_query_sql_cuts_rows_at_character_cap(mocker, query):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": "100"})
    result = query_sql(query)
    assert len(result.rows) == 4
    assert result.truncated is True
    assert result.note == (
        "Only 4 of 10 rows are shown, because an answer holds at most 100 characters. "
        "Filter or aggregate the query, or select fewer or shorter columns."
    )


def test_query_sql_shows_no_row_when_the_first_row_alone_passes_the_character_cap(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": "10"})
    result = query_sql("SELECT 'xxxxxxxxxxxxxxxxxxxx' FROM generate_series(1, 3)")
    assert result.rows == []
    assert result.truncated is True
    assert result.note == (
        "Only 0 of 3 rows are shown, because an answer holds at most 10 characters, and the "
        "first row alone holds more. Filter or aggregate the query, or select fewer or "
        "shorter columns."
    )


def count(query):
    return query_cratedb(query)["rows"][0][0]


@pytest.fixture(scope="module")
def partitions():
    query_cratedb("DROP TABLE IF EXISTS testdrive_bounds.readings")
    query_cratedb(
        "CREATE TABLE testdrive_bounds.readings (day INT) CLUSTERED INTO 1 SHARDS "
        "PARTITIONED BY (day) WITH (number_of_replicas = 0)"
    )
    query_cratedb("INSERT INTO testdrive_bounds.readings VALUES (1), (2), (3)")
    query_cratedb("REFRESH TABLE testdrive_bounds.readings")
    yield
    query_cratedb("DROP TABLE IF EXISTS testdrive_bounds.readings")


def test_cluster_health_cuts_rows_at_the_row_cap(mocker, partitions):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_ROWS": "2"})
    result = get_cluster_health()
    total = count("SELECT count(*) FROM sys.health")
    assert len(result.rows) == 2
    assert result.truncated is True
    assert result.note.startswith(
        f"Only 2 of {total} rows are shown, because an answer holds at most 2 of them."
    )


def test_list_tables_cuts_tables_at_the_row_cap(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_ROWS": "3"})
    result = list_tables("sys")
    assert len(result.tables) == 3
    assert result.truncated is True


def test_list_schemas_cuts_schemas_at_the_character_cap(mocker, answer_with):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": "100"})
    rows = [["doc", 3, 0], ["sensors", 12, 2], ["weather", 4, 0]]
    answer = {"cols": ["table_schema", "tables", "views"], "rows": rows, "rowcount": 3}
    answer_with(lambda request: httpx.Response(200, json=answer))
    result = list_schemas()
    assert [schema.schema_name for schema in result.schemas] == ["doc", "sensors"]
    assert result.truncated is True
    assert result.note == (
        "Only 2 of 3 schemas are shown, because an answer holds at most 100 characters. "
        "Query information_schema.tables with query_sql for the others."
    )


@pytest.mark.parametrize("chars", ["300", "3"], ids=["cut", "no-room"])
def test_describe_table_cuts_a_definition_above_the_character_cap(mocker, chars):
    full = describe_table("sys", "nodes").definition
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": chars})
    description = describe_table("sys", "nodes")
    assert full.startswith(description.definition.removesuffix("…"))
    assert tool.row_chars(description.definition) <= int(chars)
    assert description.truncated is True
