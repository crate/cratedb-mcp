import pytest

from cratedb_mcp.knowledge import DocumentationIndex, Queries

GITHUB_INDEX_LINK = "https://raw.githubusercontent.com/crate/crate/refs/heads/master/README.rst"


@pytest.fixture(scope="module")
def documentation_index():
    return DocumentationIndex()


def test_documentation_index():
    documentation_index = DocumentationIndex()
    titles = [item["title"] for item in documentation_index.items()]
    assert len(titles) >= 50
    assert "Welcome to CrateDB" in titles
    assert "CrateDB features" in titles
    assert "CrateDB SQL reference: Scalar functions" in titles
    assert "Guide: CrateDB query optimization" in titles


def test_url_permitted_index_link_on_other_host():
    documentation_index = DocumentationIndex()
    link = "https://www.psycopg.org/psycopg3/docs/_sources/basic/usage.rst.txt"
    assert link in [item["link"] for item in documentation_index.items()]
    assert documentation_index.url_permitted(link) is True
    assert documentation_index.url_permitted("https://www.psycopg.org/psycopg3/docs/") is False


@pytest.mark.parametrize(
    "url",
    [
        GITHUB_INDEX_LINK,
        GITHUB_INDEX_LINK + "#building-from-source",
        "https://docs.cratedb.com/projects/guide/index.html",
        "https://docs.cratedb.com/projects/guide/search.html?q=MATCH#results",
        "https://cratedb.com/docs/guide/",
    ],
    ids=[
        "index-link",
        "index-link-with-fragment",
        "page-on-docs-site",
        "page-with-query-and-fragment",
        "page-on-main-site",
    ],
)
def test_url_permitted_index_links_and_pages_on_the_sites(documentation_index, url):
    assert documentation_index.url_permitted(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://raw.githubusercontent.com/crate/crate/refs/heads/master/docs/general/builtins/scalar-functions.rst",
        GITHUB_INDEX_LINK + "?ref=other",
        "https://user@docs.cratedb.com/projects/guide/index.html",
        "https://docs.cratedb.com.example.org/",
        "https://docs.cratedb.com:8443/projects/guide/index.html",
        "http://docs.cratedb.com/projects/guide/index.html",
        "https://docs.cratedb.com:guide/",
    ],
    ids=[
        "crate-repository-file-outside-the-index",
        "index-link-with-other-query",
        "user-part-on-a-site",
        "host-that-starts-with-a-site",
        "other-port",
        "http",
        "address-that-cannot-be-parsed",
    ],
)
def test_url_permitted_refuses_other_links(documentation_index, url):
    assert documentation_index.url_permitted(url) is False


def test_permitted_sites_end_with_a_slash_so_that_a_prefix_ends_at_a_path_boundary():
    assert all(site.endswith("/") for site in DocumentationIndex.permitted_urls)


def test_queries():
    assert "information_schema.columns" in Queries.COLUMNS
    assert "information_schema.tables" in Queries.SCHEMAS
    assert "sys.health" in Queries.HEALTH
