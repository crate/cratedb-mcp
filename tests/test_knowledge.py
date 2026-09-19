import hishel
import httpx
import pytest

from cratedb_mcp.knowledge import DocumentationIndex, Queries


def test_documentation_index():
    documentation_index = DocumentationIndex()
    titles = [item["title"] for item in documentation_index.items()]
    assert len(titles) >= 50
    assert "Welcome to CrateDB" in titles
    assert "CrateDB features" in titles
    assert "CrateDB SQL reference: Scalar functions" in titles
    assert "Guide: CrateDB query optimization" in titles


def test_queries():
    assert "information_schema.columns" in Queries.TABLES_COLUMNS
    assert "information_schema.tables" in Queries.TABLES_METADATA
    assert "partitions_health" in Queries.TABLES_METADATA
    assert "sys.health" in Queries.HEALTH


def test_documentation_index_client_cached(mocker, tmp_path):
    """Verify the documentation client uses a cache within the cache directory"""
    mocker.patch("cratedb_mcp.settings.Settings.docs_cache_dir", return_value=str(tmp_path))
    client = DocumentationIndex().client
    assert isinstance(client, hishel.CacheClient)
    assert (tmp_path / "documentation.sqlite").exists()


def test_documentation_index_client_disabled(mocker, tmp_path):
    """Verify caching can be turned off"""
    mocker.patch.dict("os.environ", {"CRATEDB_MCP_DOCS_CACHE_TTL": "0"})
    mocker.patch("cratedb_mcp.settings.Settings.docs_cache_dir", return_value=str(tmp_path))
    client = DocumentationIndex().client
    assert isinstance(client, httpx.Client)
    assert not isinstance(client, hishel.CacheClient)
    assert not (tmp_path / "documentation.sqlite").exists()


def test_documentation_index_client_unavailable(mocker, tmp_path):
    """Verify an unavailable cache degrades to an uncached client"""
    cache_path = tmp_path / "file"
    cache_path.touch()
    mocker.patch("cratedb_mcp.settings.Settings.docs_cache_dir", return_value=str(cache_path))
    with pytest.warns(UserWarning) as record:
        client = DocumentationIndex().client
    assert isinstance(client, httpx.Client)
    assert not isinstance(client, hishel.CacheClient)
    assert "Cannot use documentation cache" in record[0].message.args[0]


def test_documentation_index_client_incompatible(mocker, tmp_path):
    """Verify any failure to set up the cache degrades to an uncached client"""
    mocker.patch("cratedb_mcp.settings.Settings.docs_cache_dir", return_value=str(tmp_path))
    mocker.patch("hishel.SQLiteStorage", side_effect=AttributeError("incompatible"))
    with pytest.warns(UserWarning) as record:
        client = DocumentationIndex().client
    assert isinstance(client, httpx.Client)
    assert not isinstance(client, hishel.CacheClient)
    assert "Cannot use documentation cache" in record[0].message.args[0]


def test_documentation_index_url_permitted():
    """Verify the allowlist honors path boundaries, so lookalike GitHub accounts are rejected"""
    index = DocumentationIndex()
    assert index.url_permitted("https://cratedb.com/docs/guide/index.html")
    assert index.url_permitted("https://github.com/crate/crate/blob/master/README.rst")
    assert index.url_permitted("https://raw.githubusercontent.com/crate/crate/master/README.rst")
    assert not index.url_permitted("https://github.com/crate-evil/crate/blob/master/README.rst")
    assert not index.url_permitted("https://raw.githubusercontent.com/crates/x/main/README.md")
    assert not index.url_permitted("https://cratedb.com.example.org/")


def test_documentation_index_links_permitted():
    """Verify each link advertised by the documentation index can be fetched"""
    index = DocumentationIndex()
    links = [item["link"] for item in index.items()]
    assert links
    assert [link for link in links if not index.url_permitted(link)] == []


def test_documentation_index_links_matched_exactly():
    """Verify indexed links outside the permitted prefixes do not open their whole location"""
    index = DocumentationIndex()
    link = "https://raw.githubusercontent.com/jackc/pgx/refs/heads/master/README.md"
    assert index.url_permitted(link)
    assert not index.url_permitted(link + "?foo")
    assert not index.url_permitted(link.replace("README.md", "CHANGELOG.md"))
    assert not index.url_permitted("https://raw.githubusercontent.com/jackc/evil/main/README.md")


def test_documentation_index_items_cache_lifetime(mocker):
    """Verify the cache lifetime for outline items is read at runtime"""
    index = DocumentationIndex()
    first = index.items()
    assert index.items() is first

    mocker.patch.dict("os.environ", {"CRATEDB_MCP_DOCS_CACHE_TTL": "0"})
    index._items_expiry = 0.0
    second = index.items()
    assert second is not first
    assert index.items() is not second
