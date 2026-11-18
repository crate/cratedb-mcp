import json
import os

import httpx
import pytest

from cratedb_mcp import tool
from cratedb_mcp.tool import (
    describe_table,
    explain_query,
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


ANALYZED_PLAN = {"Execute": {f"{shard}-collect": {"Query": "é" * 1_900} for shard in range(48)}}


@pytest.mark.parametrize(
    ("analyze", "plan"),
    [
        (True, ANALYZED_PLAN),
        (False, "Collect[doc.t1 | [id] | (name = '" + "é" * 60_000 + "')]"),
    ],
    ids=["analyzed", "multibyte"],
)
def test_explain_query_cuts_a_plan_above_the_character_cap(mocker, analyze, plan):
    answer = {"cols": ["QUERY PLAN"], "rows": [[plan]], "rowcount": 1, "duration": 1.0}
    mocker.patch.object(tool, "query_cratedb", return_value=answer)
    text = (
        plan
        if isinstance(plan, str)
        else json.dumps(plan, ensure_ascii=False, separators=(",", ":"))
    )
    result = explain_query("SELECT ts FROM doc.metrics", analyze=analyze)
    ((shown,),) = result.rows
    assert text.startswith(shown.removesuffix("…"))
    assert tool.row_chars([shown]) <= 50_000 < tool.row_chars([text[: len(shown)] + "…"])
    assert result.truncated is True


def test_query_sql_cuts_an_explained_plan_as_explain_query_does(mocker):
    answer = {"cols": ["QUERY PLAN"], "rows": [[ANALYZED_PLAN]], "rowcount": 1, "duration": 1.0}
    mocker.patch.object(tool, "query_cratedb", return_value=answer)
    result = query_sql("EXPLAIN ANALYZE SELECT ts FROM doc.metrics")
    assert result.truncated is True
    assert result == explain_query("SELECT ts FROM doc.metrics", analyze=True)


@pytest.mark.parametrize("chars", ["250", "60"], ids=["final-step-whole", "final-step-cut"])
def test_explain_query_keeps_the_final_step_of_a_verbose_plan_above_the_cap(mocker, chars):
    query = "SELECT mountain FROM sys.summits WHERE height > 4000"
    full = explain_query(query, verbose=True)
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": chars})
    result = explain_query(query, verbose=True)
    ((step, shown),) = result.rows
    final_step, final_plan = full.rows[-1]
    assert step == final_step == "Final logical plan"
    assert final_plan.startswith(shown.removesuffix("…"))
    assert tool.row_chars([step, shown]) <= int(chars)
    assert result.truncated is True


def test_explain_query_shows_no_plan_when_the_cap_leaves_no_room_for_it(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": "20"})
    result = explain_query("SELECT mountain FROM sys.summits", verbose=True)
    assert result.rows == []
    assert result.truncated is True


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
