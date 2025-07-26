import pytest

from cratedb_mcp.tool import (
    fetch_cratedb_docs,
    get_cluster_health,
    get_cratedb_documentation_index,
    get_table_columns,
    get_table_metadata,
    query_sql,
)


def test_get_documentation_index():
    assert len(get_cratedb_documentation_index()) >= 3


def test_fetch_docs_forbidden():
    with pytest.raises(ValueError) as ex:
        fetch_cratedb_docs("https://example.com")
    assert ex.match("Link is not permitted: https://example.com")


def test_fetch_docs_permitted_github():
    response = fetch_cratedb_docs(
        "https://raw.githubusercontent.com/crate/crate/refs/heads/5.10/docs/general/builtins/scalar-functions.rst"
    )
    assert "initcap" in response


def test_fetch_docs_permitted_cratedb_com():
    response = fetch_cratedb_docs(
        "https://cratedb.com/docs/crate/reference/en/latest/_sources/general/builtins/scalar-functions.rst.txt"
    )
    assert "initcap" in response


def test_query_sql_permitted():
    assert query_sql("SELECT 42")["rows"] == [[42]]


def test_query_sql_trailing_slash(mocker):
    """Verify that query_sql works correctly when HTTP_URL has a trailing slash."""
    mocker.patch("cratedb_mcp.tool.HTTP_URL", "http://localhost:4200/")
    assert query_sql("SELECT 42")["rows"] == [[42]]


def test_query_sql_forbidden_easy():
    with pytest.raises(PermissionError) as ex:
        assert "RelationUnknown" in str(
            query_sql("INSERT INTO foobar (id) VALUES (42) RETURNING id")
        )
    assert ex.match("Only queries that have a SELECT statement are allowed")


def test_query_sql_forbidden_sneak_value():
    with pytest.raises(PermissionError) as ex:
        query_sql("INSERT INTO foobar (operation) VALUES ('select')")
    assert ex.match("Only queries that have a SELECT statement are allowed")


def test_get_table_columns():
    response = str(get_table_columns())
    assert "information_schema" in response
    assert "pg_catalog" in response

    # Verify the returned structure.
    result = get_table_columns()
    assert isinstance(result, dict)
    expected_keys = {"user", "information_schema", "pg_catalog", "sys"}
    assert set(result.keys()) == expected_keys


def test_get_table_metadata():
    assert "partitions_health" in str(get_table_metadata())


def test_get_cluster_health():
    assert "missing_shards" in str(get_cluster_health())
