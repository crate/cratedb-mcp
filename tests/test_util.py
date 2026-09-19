import os

import pytest

from cratedb_mcp.util.sql import sql_denial_message, sql_is_permitted


def test_sql_select_permitted():
    """Regular SQL SELECT statements are permitted"""
    assert sql_is_permitted("SELECT 42") is True
    assert sql_is_permitted(" SELECT 42") is True
    assert sql_is_permitted("select 42") is True


def test_sql_select_rejected():
    """Bogus SQL SELECT statements are rejected"""
    assert sql_is_permitted(r"--\; select 42") is False


def test_sql_insert_permit_success(mocker):
    """When explicitly allowed, permit any kind of statement, but verify there is a warning"""
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_PERMIT_ALL_STATEMENTS": "true"})
    with pytest.warns(UserWarning) as record:
        assert sql_is_permitted("INSERT INTO foobar") is True
    assert "All types of SQL statements are permitted" in record[0].message.args[0]


def test_sql_insert_permit_invalid(mocker):
    """Verify invalid environment variable"""
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_PERMIT_ALL_STATEMENTS": "-555"})
    with pytest.warns(UserWarning) as record:
        assert sql_is_permitted("INSERT INTO foobar") is False
    assert (
        "Environment variable `CRATEDB_MCP_PERMIT_ALL_STATEMENTS` invalid"
        in record[0].message.args[0]
    )


def test_sql_select_multiple_rejected():
    """Multiple SQL statements are rejected"""
    assert sql_is_permitted("SELECT 42; SELECT 42;") is False


def test_sql_create_rejected():
    """DDL statements are rejected"""
    assert sql_is_permitted("CREATE TABLE foobar AS SELECT 42") is False


def test_sql_insert_rejected():
    """DML statements are rejected"""
    assert sql_is_permitted("INSERT INTO foobar") is False


def test_sql_select_into_rejected():
    """SELECT+DML statements are rejected"""
    assert sql_is_permitted("SELECT * INTO foobar FROM bazqux") is False
    assert sql_is_permitted("SELECT * FROM bazqux INTO foobar") is False
    assert sql_is_permitted("WITH FOO AS (SELECT * FROM (SELECT * bazqux INTO foobar))") is False


def test_sql_select_into_permitted():
    """Forbidden keywords do not contribute to classification when used as labels"""
    assert sql_is_permitted('SELECT * FROM "into"') is True
    assert sql_is_permitted('SELECT * FROM "INTO"') is True


def test_sql_empty_rejected():
    """Empty statements are rejected"""
    assert sql_is_permitted("") is False


def test_sql_almost_empty_rejected():
    """Quasi-empty statements are rejected"""
    assert sql_is_permitted(" ") is False


def test_sql_none_rejected():
    """Void statements are rejected"""
    assert sql_is_permitted(None) is False


def test_sql_multiple_statements_rejected():
    assert sql_is_permitted("SELECT 42; INSERT INTO foo VALUES (1)") is False


def test_sql_with_comments_rejected():
    assert (
        sql_is_permitted("/* Sneaky comment */ INSERT /* another comment */ INTO foo VALUES (1)")
        is False
    )


def test_sql_update_rejected():
    """UPDATE statements are rejected"""
    assert sql_is_permitted("UPDATE foobar SET column = 'value'") is False


def test_sql_delete_rejected():
    """DELETE statements are rejected"""
    assert sql_is_permitted("DELETE FROM foobar") is False


def test_sql_truncate_rejected():
    """TRUNCATE statements are rejected"""
    assert sql_is_permitted("TRUNCATE TABLE foobar") is False


def test_sql_drop_rejected():
    """DROP statements are rejected"""
    assert sql_is_permitted("DROP TABLE foobar") is False


def test_sql_alter_rejected():
    """ALTER statements are rejected"""
    assert sql_is_permitted("ALTER TABLE foobar ADD COLUMN newcol INTEGER") is False


def test_sql_case_manipulation_rejected():
    """Statements with case manipulation to hide intent are rejected"""
    assert sql_is_permitted("SeLeCt * FrOm users; DrOp TaBlE users") is False


def test_sql_unicode_evasion_rejected():
    """Statements with unicode characters to evade filters are rejected"""
    assert sql_is_permitted("SELECT * FROM users; \uff1b DROP TABLE users") is False


def test_sql_explain_permitted():
    """`EXPLAIN` statements are permitted when they explain read-only statements"""
    assert sql_is_permitted("EXPLAIN SELECT 42") is True
    assert sql_is_permitted("EXPLAIN SELECT * FROM foobar WHERE name = 'delete'") is True
    assert sql_is_permitted("EXPLAIN ANALYZE SELECT 42") is True


def test_sql_explain_rejected():
    """`EXPLAIN` statements are rejected when they explain write statements"""
    assert sql_is_permitted("EXPLAIN INSERT INTO foobar VALUES (42)") is False
    assert sql_is_permitted("EXPLAIN UPDATE foobar SET name = 'value'") is False
    assert sql_is_permitted("EXPLAIN DELETE FROM foobar") is False
    assert sql_is_permitted("EXPLAIN ANALYZE DELETE FROM foobar") is False


def test_sql_show_permitted():
    """`SHOW` statements are read-only, and thus permitted"""
    assert sql_is_permitted("SHOW TABLES") is True
    assert sql_is_permitted("SHOW CREATE TABLE foobar") is True
    assert sql_is_permitted("SHOW COLUMNS FROM foobar") is True


def test_sql_show_evasion_rejected():
    """`SHOW` statements do not permit chaining write statements"""
    assert sql_is_permitted("SHOW TABLES; DROP TABLE foobar") is False


def test_sql_with_permitted():
    """Common table expressions are permitted when they are read-only"""
    assert sql_is_permitted("WITH x AS (SELECT 42) SELECT * FROM x") is True


def test_sql_with_rejected():
    """Common table expressions are rejected when they smuggle in writes"""
    assert sql_is_permitted("WITH x AS (DELETE FROM foobar RETURNING id) SELECT * FROM x") is False
    assert sql_is_permitted("WITH x AS (UPDATE foobar SET name = 'v') SELECT * FROM x") is False
    assert sql_is_permitted("WITH x AS (INSERT INTO foobar VALUES (42)) SELECT * FROM x") is False


def test_sql_parenthesized_permitted():
    """Parenthesized queries are permitted"""
    assert sql_is_permitted("(SELECT 42)") is True


def test_sql_excessive_nesting_rejected():
    """Statements which can not be analyzed are denied, without raising an exception"""
    assert sql_is_permitted("SELECT " + "(" * 3000 + "1" + ")" * 3000) is False


def test_sql_explain_chain_bounded():
    """A long chain of `EXPLAIN` keywords is classified in bounded time, without recursion"""
    assert sql_is_permitted("EXPLAIN " * 3000 + "SELECT 1") is True
    assert sql_is_permitted("EXPLAIN " * 3000 + "DELETE FROM foobar") is False


def test_sql_explain_options_permitted():
    """`EXPLAIN` accepts options, the explained statement decides about the outcome"""
    assert sql_is_permitted("EXPLAIN VERBOSE SELECT 42") is True
    assert sql_is_permitted("EXPLAIN (COSTS false) SELECT 42") is True
    assert sql_is_permitted("EXPLAIN (ANALYZE true, COSTS false) SELECT 42") is True
    assert sql_is_permitted("EXPLAIN (ANALYZE) DELETE FROM foobar") is False
    assert sql_is_permitted("EXPLAIN VERBOSE DROP TABLE foobar") is False
    assert sql_is_permitted("-- comment\nEXPLAIN SELECT 42") is False


@pytest.mark.parametrize(
    "expression",
    [
        "OPTIMIZE TABLE foobar WITH (max_num_segments = 1)",
        "REFRESH TABLE foobar",
        "KILL ALL",
        "foo WITH bar AS (SELECT 1) SELECT 1",
        "foo SHOW TABLES",
        "foo SELECT 1",
        "(DELETE FROM foobar)",
    ],
)
def test_sql_classified_by_leading_token(expression):
    """Statements unknown to sqlparse are classified by their leading token, not a later keyword"""
    assert sql_is_permitted(expression) is False


def test_sql_parenthesized_query_permitted():
    assert sql_is_permitted("(SELECT 1)") is True
    assert sql_is_permitted("/* comment */ SHOW TABLES") is True


def test_sql_denial_message_not_analyzable():
    """Statements which can not be analyzed are explained using the generic message"""
    message = sql_denial_message("SELECT " + "(" * 3000 + "1" + ")" * 3000)
    assert message == "Only read-only statements (SELECT, WITH, EXPLAIN, SHOW) are permitted"
