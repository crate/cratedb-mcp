from starlette.testclient import TestClient

from cratedb_mcp.auth import BearerTokenVerifier
from cratedb_mcp.cli import http_security_options
from cratedb_mcp.core import CrateDbMcp


def http_client(allowed_hosts=(), allowed_origins=(), token=None):
    auth = BearerTokenVerifier(token) if token else None
    mcp = CrateDbMcp(auth=auth).mcp
    app = mcp.http_app(**http_security_options(allowed_hosts, allowed_origins))
    return TestClient(app, base_url="http://127.0.0.1:8000")


def test_health_answers_on_localhost():
    with http_client() as client:
        response = client.get("/health", headers={"Host": "localhost:8000"})
    assert response.status_code == 200
    assert response.text == "OK"


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
        assert client.get("/health").status_code == 200
