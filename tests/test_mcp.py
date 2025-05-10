import pytest

from cratedb_mcp.__main__ import (
    fetch_cratedb_docs,
    get_cratedb_documentation_index,
    get_health,
    get_table_metadata,
    query_sql,
)


def test_get_documentation_index():
    assert len(get_cratedb_documentation_index()) >= 3


def test_fetch_docs_forbidden():
    with pytest.raises(ValueError) as ex:
        fetch_cratedb_docs("https://cratedb.com/docs/crate/reference/en/latest/_sources/general/builtins/scalar-functions.rst.txt")
    assert ex.match("Only github cratedb links can be fetched")


def test_fetch_docs_permitted():
    response = fetch_cratedb_docs("https://raw.githubusercontent.com/crate/crate/refs/heads/5.10/docs/general/builtins/scalar-functions.rst")
    assert "initcap" in response


def test_query_sql_forbidden():
    with pytest.raises(ValueError) as ex:
        assert "RelationUnknown" in str(query_sql("INSERT INTO foobar (id) VALUES (42) RETURNING id"))
    assert ex.match("Only queries that have a SELECT statement are allowed")


def test_query_sql_permitted():
    assert query_sql("SELECT 42")["rows"] == [[42]]


def test_query_sql_permitted_exploit():
    # FIXME: Read-only protection must become stronger.
    query_sql("INSERT INTO foobar (operation) VALUES ('select')")


def test_get_table_metadata():
    assert "partitions_health" in str(get_table_metadata())


def test_get_health():
    assert "missing_shards" in str(get_health())
