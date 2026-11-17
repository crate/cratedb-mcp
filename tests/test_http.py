import asyncio
import contextlib
import threading
import time

import pytest
import uvicorn
from fastmcp import Client
from starlette.testclient import TestClient

from cratedb_mcp.auth import BearerTokenVerifier
from cratedb_mcp.cli import http_security_options
from cratedb_mcp.core import CrateDbMcp


def http_client(allowed_hosts=(), allowed_origins=(), token=None):
    auth = BearerTokenVerifier(token) if token else None
    mcp = CrateDbMcp(auth=auth).mcp
    app = mcp.http_app(**http_security_options(allowed_hosts, allowed_origins))
    return TestClient(app, base_url="http://127.0.0.1:8000")


def test_unknown_host_is_misdirected():
    with http_client() as client:
        response = client.get("/health", headers={"Host": "mcp.example.org:8000"})
    assert response.status_code == 421


def test_allowed_host_passes():
    with http_client(allowed_hosts=["mcp.example.org"]) as client:
        response = client.get("/health", headers={"Host": "mcp.example.org:8000"})
    assert response.status_code == 200


def test_foreign_origin_is_forbidden():
    with http_client() as client:
        response = client.post("/mcp", headers={"Origin": "https://attacker.example"}, json={})
    assert response.status_code == 403


def test_allowed_origin_passes_the_origin_check():
    with http_client(allowed_origins=["https://app.example.org"]) as client:
        response = client.post("/mcp", headers={"Origin": "https://app.example.org"}, json={})
    assert response.status_code != 403


def test_request_without_token_is_unauthorized():
    with http_client(token="secret") as client:
        assert client.post("/mcp", json={}).status_code == 401


def test_request_with_wrong_token_is_unauthorized():
    with http_client(token="secret") as client:
        response = client.post("/mcp", headers={"Authorization": "Bearer wrong"}, json={})
    assert response.status_code == 401


def test_request_with_token_passes_authentication():
    with http_client(token="secret") as client:
        response = client.post("/mcp", headers={"Authorization": "Bearer secret"}, json={})
    assert response.status_code not in (401, 403)


def test_health_needs_no_token():
    with http_client(token="secret") as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.text == "OK"


@contextlib.contextmanager
def served():
    app = CrateDbMcp().mcp.http_app(**http_security_options((), ()))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    thread = threading.Thread(target=server.run)
    thread.start()
    try:
        while not server.started and thread.is_alive():
            time.sleep(0.01)
        port = server.servers[0].sockets[0].getsockname()[1]
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        server.should_exit = True
        thread.join()


@pytest.mark.parametrize(
    ("mode", "version"), [("2026-07-28", "2026-07-28"), ("legacy", "2025-11-25")]
)
def test_http_serves_both_protocol_versions(mode, version):
    async def session(url):
        async with Client(url, mode=mode) as client:
            tools = await client.list_tools()
            result = await client.call_tool("get_cratedb_documentation_index", {})
            return client.protocol_version, {tool.name for tool in tools}, result

    with served() as url:
        negotiated, names, result = asyncio.run(session(url))
    assert negotiated == version
    assert "query_sql" in names
    assert result.is_error is False
