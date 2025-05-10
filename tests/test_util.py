import cratedb_mcp
from cratedb_mcp.util.sql import sql_is_permitted


def test_sql_expression_select_permitted():
    """Regular SQL SELECT statements are permitted"""
    assert sql_is_permitted("SELECT 42") is True
    assert sql_is_permitted(" SELECT 42") is True
    assert sql_is_permitted("select 42") is True


def test_sql_expression_select_rejected():
    """Bogus SQL SELECT statements are rejected"""
    assert sql_is_permitted(r"--\; select 42") is False


def test_sql_expression_insert_allowed(mocker):
    """When explicitly allowed, permit any kind of statement"""
    mocker.patch.object(cratedb_mcp.util.sql, "PERMIT_ALL_STATEMENTS", True)
    assert sql_is_permitted("INSERT INTO foobar") is True


def test_sql_expression_select_multiple_rejected():
    """Multiple SQL statements are rejected"""
    assert sql_is_permitted("SELECT 42; SELECT 42;") is False


def test_sql_expression_create_rejected():
    """DDL statements are rejected"""
    assert sql_is_permitted("CREATE TABLE foobar AS SELECT 42") is False


def test_sql_expression_insert_rejected():
    """DML statements are rejected"""
    assert sql_is_permitted("INSERT INTO foobar") is False


def test_sql_expression_select_into_rejected():
    """SELECT+DML statements are rejected"""
    assert sql_is_permitted("SELECT * INTO foobar FROM bazqux") is False
    assert sql_is_permitted("SELECT * FROM bazqux INTO foobar") is False


def test_sql_expression_empty_rejected():
    """Empty statements are rejected"""
    assert sql_is_permitted("") is False


def test_sql_expression_almost_empty_rejected():
    """Quasi-empty statements are rejected"""
    assert sql_is_permitted(" ") is False


def test_sql_expression_none_rejected():
    """Void statements are rejected"""
    assert sql_is_permitted(None) is False


def test_sql_expression_multiple_statements_rejected():
    assert sql_is_permitted("SELECT 42; INSERT INTO foo VALUES (1)") is False


def test_sql_expression_with_comments_rejected():
    assert sql_is_permitted(
        "/* Sneaky comment */ INSERT /* another comment */ INTO foo VALUES (1)") is False


def test_sql_expression_update_rejected():
    """UPDATE statements are rejected"""
    assert sql_is_permitted("UPDATE foobar SET column = 'value'") is False


def test_sql_expression_delete_rejected():
    """DELETE statements are rejected"""
    assert sql_is_permitted("DELETE FROM foobar") is False


def test_sql_expression_truncate_rejected():
    """TRUNCATE statements are rejected"""
    assert sql_is_permitted("TRUNCATE TABLE foobar") is False


def test_sql_expression_drop_rejected():
    """DROP statements are rejected"""
    assert sql_is_permitted("DROP TABLE foobar") is False


def test_sql_expression_alter_rejected():
    """ALTER statements are rejected"""
    assert sql_is_permitted("ALTER TABLE foobar ADD COLUMN newcol INTEGER") is False


def test_sql_expression_case_manipulation_rejected():
    """Statements with case manipulation to hide intent are rejected"""
    assert sql_is_permitted("SeLeCt * FrOm users; DrOp TaBlE users") is False


def test_sql_expression_unicode_evasion_rejected():
    """Statements with unicode characters to evade filters are rejected"""
    assert sql_is_permitted("SELECT * FROM users; \uFF1B DROP TABLE users") is False
