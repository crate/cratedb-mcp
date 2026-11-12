import os

import httpx
import pytest

from cratedb_mcp import tool
from cratedb_mcp.tool import explain_query, query_sql


def test_query_sql_cuts_rows_at_default_cap():
    result = query_sql("SELECT x FROM generate_series(1, 150) AS t(x)")
    assert len(result["rows"]) == 100
    assert result["truncated"] is True
    assert "Only the first 100 of 150 rows are shown, because the cap is 100 rows" in result["note"]
    assert "ask for up to 1000 rows with max_rows" in result["note"]


def test_query_sql_max_rows_raises_cap():
    result = query_sql("SELECT x FROM generate_series(1, 150) AS t(x)", max_rows=120)
    assert len(result["rows"]) == 120
    assert result["truncated"] is True


def test_query_sql_max_rows_stops_at_ceiling():
    result = query_sql("SELECT x FROM generate_series(1, 1500) AS t(x)", max_rows=5000)
    assert len(result["rows"]) == 1000
    assert "because the cap is 1000 rows" in result["note"]
    assert "max_rows" not in result["note"]


def test_query_sql_small_result_is_complete():
    result = query_sql("SELECT x FROM generate_series(1, 3) AS t(x)")
    assert result["rows"] == [[1], [2], [3]]
    assert result["truncated"] is False
    assert "note" not in result


def test_query_sql_cuts_rows_at_character_cap(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": "100"})
    result = query_sql("SELECT 'xxxxxxxxxxxxxxxxxxxx' FROM generate_series(1, 10)")
    assert len(result["rows"]) == 4
    assert "because the next row would pass 100 characters" in result["note"]
    assert "Select fewer or shorter columns" in result["note"]
    assert "max_rows" not in result["note"]


def test_query_sql_says_when_the_first_row_alone_passes_the_character_cap(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": "10"})
    result = query_sql("SELECT 'xxxxxxxxxxxxxxxxxxxx' FROM generate_series(1, 3)")
    assert result["rows"] == []
    assert result["truncated"] is True
    assert result["note"] == (
        "No rows are shown, because the first row alone holds 24 characters, more than the "
        "cap of 10. Select fewer columns or shorter values."
    )


@pytest.mark.parametrize(
    ("analyze", "advice"),
    [(True, "Explain it without `analyze`, or narrow the query."), (False, "Narrow the query.")],
)
def test_explain_query_says_when_the_plan_alone_passes_the_character_cap(mocker, analyze, advice):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": "20"})
    result = explain_query("SELECT mountain FROM sys.summits", analyze=analyze)
    assert result["rows"] == []
    assert result["truncated"] is True
    assert result["note"].startswith("No rows are shown, because the first row alone holds ")
    assert result["note"].endswith(f"characters, more than the cap of 20. {advice}")


@pytest.mark.parametrize(
    "call",
    [
        lambda: query_sql("SELECT 42"),
        lambda: explain_query("SELECT 42", analyze=True),
    ],
    ids=["query_sql", "explain_query"],
)
def test_timeout_advises_narrowing(mocker, call):
    mocker.patch.object(tool, "query_cratedb", side_effect=httpx.ReadTimeout("timed out"))
    with pytest.raises(TimeoutError) as ex:
        call()
    assert ex.match("Narrow it with a WHERE clause")


def test_query_sql_passes_crate_errors_through():
    result = query_sql("SELECT * FROM unknown_table")
    assert "RelationUnknown" in result["error"]["message"]
    assert "truncated" not in result
