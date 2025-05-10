from cratedb_mcp.knowledge import DOCUMENTATION_INDEX, Queries


def test_documentation_index():
    titles = [item["title"] for item in DOCUMENTATION_INDEX]
    assert len(titles) >= 35
    assert "CrateDB database" in titles
    assert "CrateDB features" in titles
    assert "CrateDB SQL functions" in titles
    assert "Guide: CrateDB query optimization" in titles


def test_queries():

    # Verify basic parts of the query.
    assert "information_schema.tables" in Queries.TABLES_METADATA

    # Verify other critical parts of the query.
    assert "sys.health" in Queries.TABLES_METADATA
    assert "WITH partitions_health" in Queries.TABLES_METADATA
    assert "LEFT JOIN" in Queries.TABLES_METADATA
