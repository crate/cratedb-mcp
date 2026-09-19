import os

import httpx
import pytest

from cratedb_mcp.settings import Settings


def test_settings_http_timeout_default():
    assert Settings.http_timeout() == 30.0


def test_settings_http_timeout_env_valid(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_HTTP_TIMEOUT": "42.42"})
    assert Settings.http_timeout() == 42.42


def test_settings_http_timeout_env_invalid(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_HTTP_TIMEOUT": "foo"})
    with pytest.warns(UserWarning) as record:
        assert Settings.http_timeout() == 30.0
    assert "Environment variable `CRATEDB_MCP_HTTP_TIMEOUT` invalid" in record[0].message.args[0]


def test_settings_http_timeout_env_negative(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_HTTP_TIMEOUT": "-1"})
    with pytest.warns(UserWarning) as record:
        assert Settings.http_timeout() == 30.0
    assert "Environment variable `CRATEDB_MCP_HTTP_TIMEOUT` invalid" in record[0].message.args[0]


def test_settings_cluster_url_default():
    assert Settings.cluster_url() == "http://localhost:4200"


def test_settings_cluster_url_credentials(mocker):
    """Verify credentials are not part of the connection URL."""
    mocker.patch.dict(os.environ, {"CRATEDB_CLUSTER_URL": "https://admin:s3cret@example.com:4200/"})
    assert Settings.cluster_url() == "https://example.com:4200"


def test_settings_cluster_url_trailing_slash(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_CLUSTER_URL": "http://localhost:4200/"})
    assert Settings.cluster_url() == "http://localhost:4200"


def test_settings_cluster_auth_from_url(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_CLUSTER_URL": "https://admin:s3cret@example.com:4200/"})
    auth = Settings.cluster_auth()
    assert isinstance(auth, httpx.BasicAuth)
    assert auth._auth_header == "Basic YWRtaW46czNjcmV0"


def test_settings_cluster_auth_from_env(mocker):
    mocker.patch.dict(
        os.environ,
        {
            "CRATEDB_CLUSTER_URL": "https://example.com:4200/",
            "CRATEDB_USERNAME": "read-only",
            "CRATEDB_PASSWORD": "s3cret",
        },
    )
    auth = Settings.cluster_auth()
    assert isinstance(auth, httpx.BasicAuth)
    assert auth._auth_header == "Basic cmVhZC1vbmx5OnMzY3JldA=="


def test_settings_cluster_auth_none():
    assert Settings.cluster_auth() is None


def test_settings_cluster_auth_from_url_without_password(mocker):
    """
    CrateDB users do not need to have a password, e.g. the default `crate` superuser.
    """
    mocker.patch.dict(os.environ, {"CRATEDB_CLUSTER_URL": "http://crate@localhost:4200"})
    auth = Settings.cluster_auth()
    assert isinstance(auth, httpx.BasicAuth)
    assert auth._auth_header == "Basic Y3JhdGU6"
    assert Settings.cluster_url() == "http://localhost:4200"


def test_settings_cluster_auth_from_env_without_password(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_USERNAME": "crate"})
    auth = Settings.cluster_auth()
    assert isinstance(auth, httpx.BasicAuth)
    assert auth._auth_header == "Basic Y3JhdGU6"


def test_settings_cluster_auth_password_only(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_PASSWORD": "s3cret"})
    with pytest.warns(UserWarning) as record:
        assert Settings.cluster_auth() is None
    assert "`CRATEDB_PASSWORD` is ignored" in record[0].message.args[0]


def test_settings_cluster_token(mocker):
    assert Settings.cluster_token() is None
    mocker.patch.dict(os.environ, {"CRATEDB_TOKEN": "token"})
    assert Settings.cluster_token() == "token"


def test_settings_result_max_bytes_default():
    assert Settings.result_max_bytes() == 1_000_000


def test_settings_result_max_bytes_env_valid(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_RESULT_MAX_BYTES": "4200"})
    assert Settings.result_max_bytes() == 4200


def test_settings_result_max_bytes_env_invalid(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_RESULT_MAX_BYTES": "foo"})
    with pytest.warns(UserWarning) as record:
        assert Settings.result_max_bytes() == 1_000_000
    assert (
        "Environment variable `CRATEDB_MCP_RESULT_MAX_BYTES` invalid" in record[0].message.args[0]
    )


def test_settings_docs_cache_dir():
    assert Settings.docs_cache_dir().endswith("cratedb-mcp")


@pytest.mark.parametrize("value", ["0", "-1"])
def test_settings_result_max_bytes_env_not_positive(mocker, value):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_RESULT_MAX_BYTES": value})
    with pytest.warns(UserWarning) as record:
        assert Settings.result_max_bytes() == 1_000_000
    assert (
        "Environment variable `CRATEDB_MCP_RESULT_MAX_BYTES` invalid" in record[0].message.args[0]
    )
