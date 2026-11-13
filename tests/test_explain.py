import pytest

from cratedb_mcp.tool import explain_query


def test_explain_query_returns_plan():
    result = explain_query("SELECT mountain FROM sys.summits WHERE height > 4000")
    assert result.cols == ["QUERY PLAN"]
    assert "sys.summits" in result.rows[0][0]
    assert "rows=" in result.rows[0][0]


def test_explain_query_without_costs():
    result = explain_query("SELECT mountain FROM sys.summits", costs=False)
    assert "rows=" not in result.rows[0][0]


def test_explain_query_verbose_shows_optimizer_steps():
    result = explain_query("SELECT mountain FROM sys.summits WHERE height > 4000", verbose=True)
    assert result.cols == ["STEP", "QUERY PLAN"]


def test_explain_query_analyze_returns_timings():
    result = explain_query("SELECT 42", analyze=True, costs=False)
    assert "Execute" in result.rows[0][0]


def test_explain_query_analyze_ignores_costs():
    result = explain_query("SELECT 42", analyze=True, costs=True)
    assert "Execute" in result.rows[0][0]


def test_explain_query_rejects_analyze_with_verbose():
    with pytest.raises(ValueError) as ex:
        explain_query("SELECT 42", analyze=True, verbose=True)
    assert ex.match("cannot combine")


def test_explain_query_rejects_writes():
    with pytest.raises(PermissionError):
        explain_query("INSERT INTO foobar (id) VALUES (42)")
