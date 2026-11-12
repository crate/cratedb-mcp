from cratedb_mcp.knowledge import DocumentationIndex, Queries


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


def test_queries():
    assert "information_schema.columns" in Queries.COLUMNS
    assert "information_schema.tables" in Queries.TABLES_METADATA
    assert "partitions_health" in Queries.TABLES_METADATA
    assert "sys.health" in Queries.HEALTH
