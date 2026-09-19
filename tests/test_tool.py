import json
import sqlite3

import httpx
import pytest
from fastmcp.exceptions import ToolError

from cratedb_mcp import tool
from cratedb_mcp.tool import (
    fetch_cratedb_docs,
    get_cluster_version,
    get_table_columns,
    query_cratedb,
    query_sql,
)


def make_client(handler) -> httpx.Client:
    """
    Create an HTTP client, backed by a mock transport.
    """
    return httpx.Client(
        base_url="http://localhost:4200",
        transport=httpx.MockTransport(handler),
    )


def test_http_client_credentials(mocker):
    """
    Verify the CrateDB client is configured with a sanitized URL and credentials.
    """
    mocker.patch.dict(
        "os.environ", {"CRATEDB_CLUSTER_URL": "https://admin:s3cret@example.com:4200/"}
    )
    with tool._http_client() as client:
        assert str(client.base_url) == "https://example.com:4200"
        assert isinstance(client.auth, httpx.BasicAuth)


def test_http_client_token(mocker):
    """
    Verify a bearer token takes precedence over basic authentication.
    """
    mocker.patch.dict(
        "os.environ",
        {
            "CRATEDB_CLUSTER_URL": "https://admin:s3cret@example.com:4200/",
            "CRATEDB_TOKEN": "token",
        },
    )
    with tool._http_client() as client:
        assert client.auth is None
        assert client.headers["Authorization"] == "Bearer token"


def test_query_cratedb_error_envelope(mocker):
    """
    CrateDB reports statement errors as an error object, they must not be masked as results.
    """

    def handler(request):
        return httpx.Response(
            400,
            json={
                "error": {
                    "message": "Relation 'nope' unknown",
                    "code": 4041,
                    "type": "RelationUnknown",
                },
                "error_trace": "io.crate.exceptions.RelationUnknown: ...",
            },
        )

    mocker.patch("cratedb_mcp.tool._http_client", return_value=make_client(handler))
    with pytest.raises(ToolError) as ex:
        query_cratedb("SELECT * FROM nope")
    assert "CrateDB error 4041: Relation 'nope' unknown" in str(ex.value)
    assert "error_trace" not in str(ex.value)


def test_query_cratedb_error_non_json(mocker):
    """
    Non-JSON error responses, e.g. from a reverse proxy, give an actionable message.
    """

    def handler(request):
        return httpx.Response(502, text="<html>Bad Gateway</html>")

    mocker.patch("cratedb_mcp.tool._http_client", return_value=make_client(handler))
    with pytest.raises(ToolError) as ex:
        query_cratedb("SELECT 1")
    assert "HTTP 502" in str(ex.value)


def test_query_cratedb_http_error(mocker):
    """
    CrateDB error responses without an error object are reported along with the status code.
    """

    def handler(request):
        return httpx.Response(404, json={"message": "not found"})

    mocker.patch("cratedb_mcp.tool._http_client", return_value=make_client(handler))
    with pytest.raises(httpx.HTTPStatusError) as ex:
        query_cratedb("SELECT 1")
    assert "404" in str(ex.value)


def test_query_cratedb_result(mocker):
    """
    Successful responses are passed through, without leaking server internals.
    """

    def handler(request):
        assert request.url.path == "/_sql"
        return httpx.Response(200, json={"cols": ["x"], "rows": [[42]], "error_trace": "internal"})

    mocker.patch("cratedb_mcp.tool._http_client", return_value=make_client(handler))
    response = query_cratedb("SELECT 42")
    assert response == {"cols": ["x"], "rows": [[42]]}


def test_query_sql_result_too_large(mocker):
    """
    Result sets beyond the configured maximum size are rejected, with guidance to refine.
    """
    mocker.patch.dict("os.environ", {"CRATEDB_MCP_RESULT_MAX_BYTES": "100"})

    def handler(request):
        return httpx.Response(200, json={"cols": ["x"], "rows": [["x" * 1000]]})

    mocker.patch("cratedb_mcp.tool._http_client", return_value=make_client(handler))
    with pytest.raises(ToolError) as ex:
        query_sql("SELECT 1")
    assert "exceeds the configured maximum of 100 bytes" in str(ex.value)
    assert "adding a LIMIT clause" in str(ex.value)


def test_get_cluster_version(mocker):
    """
    Inspect the cluster version from the CrateDB root endpoint.
    """

    def handler(request):
        assert request.url.path == "/"
        return httpx.Response(200, json={"name": "CrateDB", "version": {"number": "6.2.0"}})

    mocker.patch("cratedb_mcp.tool._http_client", return_value=make_client(handler))
    assert get_cluster_version() == "6.2.0"


def test_get_cluster_version_unavailable(mocker):
    """
    Unexpected payloads do not blow up, the version is reported as unknown.
    """

    def handler(request):
        return httpx.Response(200, json={"name": "CrateDB"})

    mocker.patch("cratedb_mcp.tool._http_client", return_value=make_client(handler))
    assert get_cluster_version() == "unknown"


def test_fetch_cratedb_docs_not_permitted():
    """
    Only documentation links from permitted domains are acquired.
    """
    with pytest.raises(ValueError) as ex:
        fetch_cratedb_docs("https://example.com/docs.txt")
    assert "Link is not permitted" in str(ex.value)


def test_fetch_cratedb_docs_error(mocker):
    """
    Failed documentation downloads are reported, instead of returning an error page.
    """

    def handler(request):
        return httpx.Response(404, text="Not Found")

    mocker.patch.object(tool.documentation_index, "_client", make_client(handler))
    with pytest.raises(httpx.HTTPStatusError):
        fetch_cratedb_docs("https://cratedb.com/docs/unknown.txt")


def test_fetch_cratedb_docs_result_too_large(mocker):
    """
    Documentation pages beyond the configured maximum size are rejected.
    """
    mocker.patch.dict("os.environ", {"CRATEDB_MCP_RESULT_MAX_BYTES": "100"})

    def handler(request):
        return httpx.Response(200, text="x" * 1000)

    mocker.patch.object(tool.documentation_index, "_client", make_client(handler))
    with pytest.raises(ToolError) as ex:
        fetch_cratedb_docs("https://cratedb.com/docs/page.txt")
    assert "exceeds the configured maximum of 100 bytes" in str(ex.value)


def test_fetch_cratedb_docs_result(mocker):
    """
    Documentation pages are returned verbatim.
    """

    def handler(request):
        return httpx.Response(200, text="About CrateDB")

    mocker.patch.object(tool.documentation_index, "_client", make_client(handler))
    assert fetch_cratedb_docs("https://cratedb.com/docs/page.txt") == "About CrateDB"


@pytest.mark.parametrize(
    "payload, message",
    [
        ([], "unexpected JSON payload of type `list`"),
        ("oops", "unexpected JSON payload of type `str`"),
        ({"error": "boom"}, "CrateDB error: boom"),
    ],
)
def test_query_cratedb_unexpected_payload(mocker, payload, message):
    """
    Unexpected JSON documents, e.g. from intermediaries, are reported as tool errors.
    """

    def handler(request):
        return httpx.Response(502, json=payload)

    mocker.patch("cratedb_mcp.tool._http_client", return_value=make_client(handler))
    with pytest.raises(ToolError) as ex:
        query_cratedb("SELECT 42")
    assert message in str(ex.value)


def test_query_cratedb_result_not_consumed_beyond_limit(mocker):
    """
    Oversized results are abandoned while streaming, instead of being loaded completely.
    """
    mocker.patch.dict("os.environ", {"CRATEDB_MCP_RESULT_MAX_BYTES": "100"})
    consumed = []

    def body():
        for _ in range(1000):
            consumed.append(1)
            yield b"x" * 100

    def handler(request):
        return httpx.Response(200, content=body())

    mocker.patch("cratedb_mcp.tool._http_client", return_value=make_client(handler))
    with pytest.raises(ToolError) as ex:
        query_cratedb("SELECT 42")
    assert "exceeds the configured maximum of 100 bytes" in str(ex.value)
    assert len(consumed) < 10


def test_query_cratedb_result_size_counts_bytes(mocker):
    """
    The result size limit applies to bytes on the wire, non-ASCII text is not inflated.
    """
    mocker.patch.dict("os.environ", {"CRATEDB_MCP_RESULT_MAX_BYTES": "100"})
    body = '{"rows": [["' + "ü" * 30 + '"]]}'

    def handler(request):
        return httpx.Response(200, content=body.encode("utf-8"))

    mocker.patch("cratedb_mcp.tool._http_client", return_value=make_client(handler))
    assert query_cratedb("SELECT 42") == {"rows": [["ü" * 30]]}
    assert tool._result_size({"rows": [["ü" * 30]]}) == 76


def test_shared_client_reused(mocker):
    """
    Tool invocations reuse a single HTTP client, until its settings change.
    """
    first = tool._shared_client()
    assert tool._shared_client() is first

    mocker.patch.dict("os.environ", {"CRATEDB_CLUSTER_URL": "https://example.com:4200"})
    second = tool._shared_client()
    assert second is not first
    assert str(second.base_url) == "https://example.com:4200"


def test_shared_client_rebuilt_when_closed():
    first = tool._shared_client()
    first.close()
    assert tool._shared_client() is not first


def test_get_table_columns_omits_oversized_sections(mocker):
    """
    Large schemas do not fail the tool altogether, oversized sections are omitted with guidance.
    """
    mocker.patch.dict("os.environ", {"CRATEDB_MCP_RESULT_MAX_BYTES": "1000"})

    def handler(request):
        stmt = json.loads(request.content)["stmt"]
        if "table_schema = 'sys'" in stmt:
            return httpx.Response(200, json={"rows": [["x" * 5000]]})
        if "table_schema = 'pg_catalog'" in stmt:
            return httpx.Response(200, json={"rows": [["x" * 600]]})
        return httpx.Response(200, json={"rows": [["x" * 300]]})

    mocker.patch("cratedb_mcp.tool._http_client", return_value=make_client(handler))
    response = get_table_columns()
    assert response["user"] == {"rows": [["x" * 300]]}
    assert response["information_schema"] == {"rows": [["x" * 300]]}
    # Fits the limit on its own, but not the remaining budget.
    assert "information_schema.columns" in response["pg_catalog"]["omitted"]
    # Exceeds the limit on its own.
    assert "table_schema = 'sys'" in response["sys"]["omitted"]


def test_fetch_cratedb_docs_cache_failure(mocker):
    """
    When the cache fails while serving a request, the page is fetched without it.
    """

    class FailingClient:
        def stream(self, *args, **kwargs):
            raise sqlite3.OperationalError("database is locked")

        def close(self):
            pass

    def handler(request):
        return httpx.Response(200, text="About CrateDB")

    mocker.patch.object(tool.documentation_index, "_client", FailingClient())
    mocker.patch("cratedb_mcp.knowledge.httpx.Client", return_value=make_client(handler))
    with pytest.warns(UserWarning) as record:
        assert fetch_cratedb_docs("https://cratedb.com/docs/page.txt") == "About CrateDB"
    assert "Documentation cache failed: database is locked" in record[0].message.args[0]


def test_query_sql_denied_with_guidance():
    """
    Reserved words used as identifiers are denied, the message explains how to proceed.
    """
    with pytest.raises(PermissionError) as ex:
        query_sql("SELECT * FROM t ORDER BY update")
    assert "includes the keyword `UPDATE`" in str(ex.value)
    assert "double quotes" in str(ex.value)

    with pytest.raises(PermissionError) as ex:
        query_sql("SELECT 1; DROP TABLE t")
    assert "Multiple statements are not permitted" in str(ex.value)

    with pytest.raises(PermissionError) as ex:
        query_sql("DROP TABLE t")
    assert str(ex.value) == "Only read-only statements (SELECT, WITH, EXPLAIN, SHOW) are permitted"


def test_fetch_cratedb_docs_unknown_charset(mocker):
    """
    Documentation pages announcing an unknown character set are decoded as UTF-8.
    """

    def handler(request):
        return httpx.Response(
            200,
            content="About CrateDB ✓".encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=unknown-charset"},
        )

    mocker.patch.object(tool.documentation_index, "_client", make_client(handler))
    assert fetch_cratedb_docs("https://cratedb.com/docs/page.txt") == "About CrateDB ✓"


def test_query_sql_denied_explain_with_guidance():
    """
    The guidance about reserved words also applies to explained statements.
    """
    with pytest.raises(PermissionError) as ex:
        query_sql("EXPLAIN SELECT count(*) AS delete FROM t")
    assert "includes the keyword `DELETE`" in str(ex.value)
