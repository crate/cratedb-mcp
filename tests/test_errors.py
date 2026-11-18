import asyncio

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
    ],
    ids=[
        "crate-error",
        "refused-statement",
        "unanalyzable-statement",
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
