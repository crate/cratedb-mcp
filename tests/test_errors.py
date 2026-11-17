import asyncio
import os

import httpx
import pytest
from fastmcp import Client

from cratedb_mcp import tool
from cratedb_mcp.core import CrateDbMcp


def call(name, arguments):
    async def run():
        async with Client(CrateDbMcp().mcp) as client:
            return await client.call_tool(name, arguments, raise_on_error=False)

    result = asyncio.run(run())
    return result.is_error, " ".join(content.text for content in result.content)


@pytest.mark.parametrize(
    ("name", "arguments", "message"),
    [
        (
            "query_sql",
            {"query": "SELECT * FROM doc.unknown_table"},
            "RelationUnknown[Relation 'doc.unknown_table' unknown] (error code 4041)",
        ),
        (
            "query_sql",
            {"query": "DELETE FROM doc.unknown_table"},
            "Only queries that have a SELECT statement are allowed.",
        ),
        (
            "query_sql",
            {"query": "SELECT " + "(" * 200 + "1" + ")" * 200},
            "The read-only check cannot analyze this statement: Maximum grouping depth "
            "exceeded (100). Shorten it, or split it into smaller queries.",
        ),
        (
            "describe_table",
            {"schema": "doc", "table": "unknown_table"},
            "Table or view not found: doc.unknown_table",
        ),
    ],
    ids=[
        "crate-error",
        "refused-statement",
        "unanalyzable-statement",
        "unknown-table",
    ],
)
def test_failed_call_sets_the_error_flag_and_carries_the_message(name, arguments, message):
    assert call(name, arguments) == (True, message)


NARROW_TIMEOUT = (
    "The query did not finish within the 30-second timeout. Narrow it with a WHERE clause, "
    "an aggregation or a LIMIT instead of running it again."
)
PLAIN_TIMEOUT = "CrateDB did not answer within the 30-second timeout."


@pytest.mark.parametrize(
    ("name", "arguments", "message"),
    [
        ("query_sql", {"query": "SELECT 42"}, NARROW_TIMEOUT),
        ("list_schemas", {}, PLAIN_TIMEOUT),
        ("describe_table", {"schema": "doc", "table": "t"}, PLAIN_TIMEOUT),
        ("get_cluster_health", {}, PLAIN_TIMEOUT),
    ],
)
def test_timeout_fails_the_call_with_advice_only_for_the_model_query(
    mocker, name, arguments, message
):
    mocker.patch.object(tool, "query_cratedb", side_effect=httpx.ReadTimeout("timed out"))
    assert call(name, arguments) == (True, message)


@pytest.mark.parametrize(
    ("status", "body", "content_type", "message"),
    [
        (
            401,
            b'password authentication failed for user "mcp"\n',
            "text/plain",
            'CrateDB answered HTTP 401: password authentication failed for user "mcp"',
        ),
        (
            502,
            b"<html><body><h1>502 Bad Gateway</h1></body></html>",
            "text/html",
            "CrateDB answered HTTP 502: <html><body><h1>502 Bad Gateway</h1></body></html>",
        ),
        (502, b"", "text/plain", "CrateDB answered HTTP 502."),
        (503, b"x" * 1_000, "text/plain", "CrateDB answered HTTP 503: " + "x" * 200 + "…"),
    ],
    ids=["unauthorized", "proxy-page", "empty", "long"],
)
def test_answer_that_is_not_json_fails_with_status_and_body_only(
    mocker, answer_with, status, body, content_type, message
):
    mocker.patch.object(tool, "HTTP_URL", "http://mcp:s3cret-pw@crate.example:4200")
    response = httpx.Response(status, content=body, headers={"Content-Type": content_type})
    answer_with(lambda request: response)
    assert call("query_sql", {"query": "SELECT 1"}) == (True, message)


def test_long_crate_error_is_cut_to_the_character_cap(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": "100"})
    is_error, text = call("query_sql", {"query": "SELECT CAST(repeat('x', 1000) AS INTEGER)"})
    message, code = text.rsplit(" (error code ", 1)
    assert is_error is True
    assert message.startswith("SQLParseException[Cannot cast `'xxx")
    assert len(message) == 101
    assert message.endswith("x…")
    assert code == "4000)"


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("query_sql", {"query": "SELECT x FROM generate_series(1, 150) AS t(x)"}),
        ("list_schemas", {"include_system": True}),
        ("list_tables", {"schema": "sys"}),
        ("describe_table", {"schema": "sys", "table": "nodes"}),
    ],
)
def test_cut_result_succeeds_and_says_so(mocker, name, arguments):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_ROWS": "2", "CRATEDB_MCP_MAX_CHARS": "200"})
    is_error, text = call(name, arguments)
    assert is_error is False
    assert '"truncated":true' in text
    assert '"note":' in text


@pytest.mark.parametrize("limit", [0, -1])
def test_query_sql_fails_a_limit_below_one(limit):
    is_error, text = call("query_sql", {"query": "SELECT 42", "limit": limit})
    assert is_error is True
    assert "limit\n  Input should be greater than or equal to 1" in text
