from cratedb_mcp.knowledge import DOCUMENTATION_INDEX, Queries


def test_documentation_index():
    assert len(DOCUMENTATION_INDEX) == 3
    assert DOCUMENTATION_INDEX[1]["name"] == "scalar functions"
    assert DOCUMENTATION_INDEX[2]["name"] == "optimize query 101"


def test_queries():
    assert "information_schema.tables" in Queries.TABLES_METADATA
