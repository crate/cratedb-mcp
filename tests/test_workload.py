import os
import threading
import time

import pytest

from cratedb_mcp import tool
from cratedb_mcp.knowledge import Queries
from cratedb_mcp.tool import diagnose_workload, query_cratedb

LONG_STATEMENT = "SELECT x / (x - 1), '" + "x" * 3000 + "' FROM generate_series(1, 2) AS t(x)"


def test_diagnose_workload_reports_log_settings_and_user():
    result = diagnose_workload("summary")
    assert result.stats_enabled is True
    assert result.jobs_log_size > 0
    assert result.user == "crate"


def test_slow_view_lists_slowest_first():
    result = diagnose_workload("slow", limit=20)
    assert result.cols == ["ended", "duration_ms", "username", "stmt", "failed"]
    durations = [row[1] for row in result.rows]
    assert durations
    assert durations == sorted(durations, reverse=True)


def test_slow_view_lists_data_statements_only():
    query_cratedb("CREATE TABLE testdrive_workload.marker (id INT)")
    query_cratedb("REFRESH TABLE testdrive_workload.marker")
    query_cratedb("DROP TABLE testdrive_workload.marker")
    query = "SELECT count(*), 'marker' FROM generate_series(1, 5000163)"
    query_cratedb(query)
    statements = [row[3] for row in diagnose_workload("slow", limit=100, since_minutes=1).rows]
    assert query in statements
    assert not [statement for statement in statements if "testdrive_workload.marker" in statement]


def test_failed_view_lists_recent_failures_with_cut_statements():
    query_cratedb(LONG_STATEMENT)
    result = diagnose_workload("failed", limit=100, since_minutes=5)
    assert all(row[4] is True for row in result.rows)
    ended = [row[0] for row in result.rows]
    assert ended == sorted(ended, reverse=True)
    statements = [row[3] for row in result.rows]
    assert LONG_STATEMENT[:1000] + "…" in statements


def test_failed_view_leaves_error_messages_out():
    query_cratedb("SELECT x / (x - 1) FROM generate_series(1, 2) AS t(x)")
    result = diagnose_workload("failed", limit=100, since_minutes=5)
    assert result.rows
    assert "by zero" not in result.model_dump_json()


def test_running_view_lists_other_data_statements_but_not_itself():
    statement = "SELECT count(*) FROM generate_series(1, 40000163)"
    explain = "EXPLAIN ANALYZE SELECT count(*) FROM generate_series(1, 60000163)"
    workers = [
        threading.Thread(target=query_cratedb, args=(text,)) for text in (explain, statement)
    ]
    for worker in workers:
        worker.start()
    try:
        for _ in range(50):
            result = diagnose_workload("running", limit=100)
            if any(row[3] == statement for row in result.rows):
                break
            time.sleep(0.05)
        else:
            pytest.fail("The running statement was not listed")
    finally:
        for worker in workers:
            worker.join()
    assert result.cols == ["started", "running_ms", "username", "stmt"]
    assert Queries.JOBS not in [row[3] for row in result.rows]
    assert explain not in [row[3] for row in result.rows]


def test_summary_view_orders_statement_types_by_total_time():
    result = diagnose_workload("summary", limit=100)
    assert "p90_ms" in result.cols
    totals = [row[result.cols.index("total_ms")] for row in result.rows]
    assert totals
    assert totals == sorted(totals, reverse=True)


@pytest.mark.parametrize(
    "max_rows, limit, sent", [("100", 0, 1), ("100", 10_000, 100), ("5000", 10_000, 1000)]
)
def test_limit_stays_within_one_the_row_cap_and_the_row_ceiling(mocker, max_rows, limit, sent):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_ROWS": max_rows})
    query = mocker.spy(tool, "query_result")
    assert diagnose_workload("summary", limit=limit).rows
    assert query.call_args.args[1] == [sent]


@pytest.mark.parametrize("minutes", [-5, 10**15])
def test_since_minutes_stays_within_a_minute_and_a_year(minutes):
    result = diagnose_workload("slow", since_minutes=minutes)
    assert result.cols
    assert result.note is None


@pytest.mark.parametrize(
    "chars, note",
    [
        ("15", "Only 1 of 2 rows are shown, because the next row would pass 15 characters."),
        (
            "5",
            "No rows are shown, because the first row alone holds 10 characters, more than "
            "the cap of 5.",
        ),
    ],
)
def test_diagnose_workload_honors_character_cap(mocker, chars, note):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": chars})
    real_result = tool.query_result

    def two_rows(query, args=None):
        if query == Queries.STATS:
            return real_result(query, args)
        return {"cols": ["statement"], "rows": [["abcdef"], ["ghijkl"]]}

    mocker.patch.object(tool, "query_result", side_effect=two_rows)
    result = diagnose_workload("summary")
    assert result.truncated is True
    assert result.note == note


def test_diagnose_workload_without_access_to_sys_tables(mocker):
    real_query = tool.query_cratedb

    def refuse_sys(query, args=None):
        if "sys." in query:
            return {"error": {"message": "SchemaUnknownException[Schema 'sys' unknown]"}}
        return real_query(query, args)

    mocker.patch.object(tool, "query_cratedb", side_effect=refuse_sys)
    result = diagnose_workload("failed")
    assert result.rows == []
    assert result.stats_enabled is None
    assert "Schema 'sys' unknown" in result.note
