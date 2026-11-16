import os

import pytest

from cratedb_mcp.tool import (
    documentation_index,
    get_cluster_health,
    get_cratedb_documentation_index,
    query_cratedb,
    query_sql,
)


def test_query_sql_cuts_rows_at_default_cap():
    result = query_sql("SELECT x FROM generate_series(1, 150) AS t(x)")
    assert len(result.rows) == 100
    assert result.truncated is True
    assert "Only the first 100 of 150 rows are shown, because the cap is 100 rows" in result.note
    assert "ask for up to 1000 rows with max_rows" in result.note


def test_query_sql_max_rows_raises_cap():
    result = query_sql("SELECT x FROM generate_series(1, 150) AS t(x)", max_rows=120)
    assert len(result.rows) == 120
    assert result.truncated is True


def test_query_sql_max_rows_stops_at_ceiling():
    result = query_sql("SELECT x FROM generate_series(1, 1500) AS t(x)", max_rows=5000)
    assert len(result.rows) == 1000
    assert "because the cap is 1000 rows" in result.note
    assert "max_rows" not in result.note


def test_query_sql_configured_cap_may_pass_ceiling(monkeypatch):
    monkeypatch.setenv("CRATEDB_MCP_MAX_ROWS", "1200")
    result = query_sql("SELECT x FROM generate_series(1, 1500) AS t(x)")
    assert len(result.rows) == 1200
    assert "because the cap is 1200 rows" in result.note
    assert "max_rows" not in result.note


def test_query_sql_small_result_is_complete():
    result = query_sql("SELECT x FROM generate_series(1, 3) AS t(x)")
    assert result.rows == [[1], [2], [3]]
    assert result.truncated is False
    assert result.note is None


def test_query_sql_cuts_rows_at_character_cap(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": "100"})
    result = query_sql("SELECT 'xxxxxxxxxxxxxxxxxxxx' FROM generate_series(1, 10)")
    assert len(result.rows) == 4
    assert "because the next row would pass 100 characters" in result.note
    assert "Select fewer or shorter columns" in result.note
    assert "max_rows" not in result.note


def test_query_sql_says_when_the_first_row_alone_passes_the_character_cap(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": "10"})
    result = query_sql("SELECT 'xxxxxxxxxxxxxxxxxxxx' FROM generate_series(1, 3)")
    assert result.rows == []
    assert result.truncated is True
    assert result.note == (
        "No rows are shown, because the first row alone holds 24 characters, more than the "
        "cap of 10. Select fewer columns or shorter values."
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


def test_cluster_health_cuts_rows_at_the_row_cap_most_severe_first(mocker, partitions):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_ROWS": "2"})
    result = get_cluster_health()
    total = count("SELECT count(*) FROM sys.health")
    assert len(result.rows) == 2
    assert result.truncated is True
    assert result.note == (
        f"Only the first 2 of {total} rows are shown, "
        "because the cap is 2 rows. Rows come most severe first, so none of the others is "
        "worse than the last one shown. Query sys.health with query_sql, filtered by "
        "table_schema, table_name or health, for the others."
    )


def test_cluster_health_says_nothing_of_rows_shown_when_none_is_shown(mocker, partitions):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": "10"})
    result = get_cluster_health()
    assert result.rows == []
    assert result.note.startswith("No rows are shown, because the first row alone holds ")
    assert result.note.endswith(
        "more than the cap of 10. Query sys.health with query_sql, filtered by table_schema, "
        "table_name or health, for the others."
    )


def test_documentation_index_cuts_pages_at_the_character_cap_only(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_ROWS": "1", "CRATEDB_MCP_MAX_CHARS": "2000"})
    index = get_cratedb_documentation_index()
    assert 1 < len(index.pages) < len(documentation_index.items())
    assert index.truncated is True
    assert index.note == (
        f"Only the first {len(index.pages)} of {len(documentation_index.items())} pages are "
        "shown, because the next page would pass 2000 characters. Choose from the pages shown."
    )


def test_documentation_index_says_nothing_of_pages_shown_when_none_is_shown(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": "10"})
    index = get_cratedb_documentation_index()
    assert index.pages == []
    assert index.note.startswith("No pages are shown, because the first page alone holds ")
    assert index.note.endswith(" characters, more than the cap of 10.")
