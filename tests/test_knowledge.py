from cratedb_mcp.knowledge import DOCUMENTATION_INDEX, Queries


def test_documentation_index():
    assert len(DOCUMENTATION_INDEX) == 3
    assert DOCUMENTATION_INDEX[1]["name"] == "scalar functions"
    assert DOCUMENTATION_INDEX[2]["name"] == "optimize query 101"


def test_queries():

    # Verify basic parts of the query.
    assert "information_schema.tables" in Queries.TABLES_METADATA

    # Verify other critical parts of the query.
    assert "sys.health" in Queries.TABLES_METADATA
    assert "WITH partitions_health" in Queries.TABLES_METADATA
    assert "LEFT JOIN" in Queries.TABLES_METADATA
