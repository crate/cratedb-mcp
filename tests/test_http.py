from starlette.testclient import TestClient

from cratedb_mcp.cli import http_security_options
from cratedb_mcp.core import CrateDbMcp


def http_client(allowed_hosts=(), allowed_origins=()):
    app = CrateDbMcp().mcp.http_app(**http_security_options(allowed_hosts, allowed_origins))
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
