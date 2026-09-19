import pytest

from cratedb_mcp import tool


@pytest.fixture(autouse=True)
def reset_shared_client():
    """
    Tool invocations share an HTTP client, make sure it does not leak between test cases.
    """
    yield
    for client in tool._client_cache.values():
        client.close()
    tool._client_cache.clear()
