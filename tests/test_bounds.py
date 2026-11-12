import os

import httpx
import pytest

from cratedb_mcp import tool
from cratedb_mcp.settings import Settings
from cratedb_mcp.tool import query_sql


def test_query_sql_cuts_rows_at_default_cap():
    result = query_sql("SELECT x FROM generate_series(1, 150) AS t(x)")
    assert len(result["rows"]) == 100
    assert result["truncated"] is True
    assert "Only the first 100 of 150 rows are shown, because the cap is 100 rows" in result["note"]


def test_query_sql_max_rows_raises_cap():
    result = query_sql("SELECT x FROM generate_series(1, 150) AS t(x)", max_rows=120)
    assert len(result["rows"]) == 120
    assert result["truncated"] is True


def test_query_sql_max_rows_stops_at_ceiling():
    result = query_sql("SELECT x FROM generate_series(1, 1500) AS t(x)", max_rows=5000)
    assert len(result["rows"]) == 1000


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


def test_query_sql_timeout_advises_narrowing(mocker):
    mocker.patch.object(tool, "query_cratedb", side_effect=httpx.ReadTimeout("timed out"))
    with pytest.raises(TimeoutError) as ex:
        query_sql("SELECT 42")
    assert ex.match("Narrow it with a WHERE clause")


def test_max_rows_setting_invalid(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_ROWS": "many"})
    with pytest.warns(UserWarning, match="CRATEDB_MCP_MAX_ROWS"):
        assert Settings.max_rows() == 100
