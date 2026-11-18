import os

import pytest
from fastmcp.exceptions import ToolError

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
    with pytest.raises(ToolError) as ex:
        explain_query("SELECT 42", analyze=True, verbose=True)
    assert ex.match("cannot combine")


@pytest.mark.parametrize(
    "query",
    ["INSERT INTO foobar (id) VALUES (42)", "SHOW TABLES", "(ANALYZE true) SELECT 42"],
)
def test_explain_query_rejects_statements_it_cannot_explain(query):
    with pytest.raises(ToolError) as ex:
        explain_query(query)
    assert ex.match("Only one SELECT, WITH or VALUES statement can be explained")


def test_explain_query_rejects_explain():
    with pytest.raises(ToolError) as ex:
        explain_query("EXPLAIN SELECT 42")
    assert ex.match("without EXPLAIN")


def test_explain_query_fails_on_a_statement_it_cannot_analyze_when_all_are_permitted(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_PERMIT_ALL_STATEMENTS": "true"})
    with pytest.warns(UserWarning), pytest.raises(ToolError) as ex:
        explain_query("SELECT " + "(" * 200 + "1" + ")" * 200)
    assert ex.match(
        r"^The read-only check cannot analyze this statement: it nests parentheses or subqueries "
        r"more than 100 levels deep\. Flatten the nesting, or split it into smaller queries\.$"
    )
