import dataclasses
import logging
import re
import typing as t

import sqlparse
from sqlparse.exceptions import SQLParseError
from sqlparse.tokens import Comment, Keyword

from cratedb_mcp.settings import Settings

logger = logging.getLogger(__name__)


def sql_is_permitted(expression: str) -> bool:
    """
    Validate the SQL expression, only permit read queries by default.

    When the `CRATEDB_MCP_PERMIT_ALL_STATEMENTS` environment variable is set,
    allow all types of statements. This is **not** recommended.

    FIXME: This is not a security boundary, it only complements a database user
           equipped with DQL privileges only.
           Issue:    https://github.com/crate/cratedb-mcp/issues/10
           Question: Does SQLAlchemy provide a solid read-only mode, or any other library?
    """
    try:
        is_dql = SqlStatementClassifier(
            expression=expression, permit_all=Settings.permit_all_statements()
        ).is_dql
    except (SQLParseError, RecursionError) as e:
        # Statements which can not be analyzed, e.g. excessively nested ones, are denied.
        logger.warning(f"Unable to analyze SQL expression: {e}")
        is_dql = False
    if is_dql:
        logger.info(f"Permitted SQL expression: {expression and expression[:50]}...")
    else:
        logger.warning(f"Denied SQL expression: {expression and expression[:50]}...")
    return is_dql


def sql_denial_message(expression: str) -> str:
    """
    Explain why an SQL expression was denied, so the LLM can correct its statement.

    Reserved words used as identifiers are a common reason, e.g. `SELECT update FROM t`.
    """
    message = "Only read-only statements (SELECT, WITH, EXPLAIN, SHOW) are permitted"
    try:
        classifier = SqlStatementClassifier(expression=expression)
        if classifier.is_evasive:
            return f"{message}. Multiple statements are not permitted"
        if classifier.operation == "EXPLAIN":
            classifier = classifier.explained
        if classifier.operation in classifier.permitted_operations:
            keyword = "INTO" if classifier.is_select_into else classifier.mutation_keyword
            if keyword:
                return (
                    f"{message}. The statement includes the keyword `{keyword}`. "
                    f"If it is meant to be an identifier, please wrap it into double quotes"
                )
    except (SQLParseError, RecursionError, IndexError):
        pass
    return message


@dataclasses.dataclass
class SqlStatementClassifier:
    """
    Helper to classify an SQL statement.

    Here, most importantly: Provide the `is_dql` property that
    signals truthfulness for read-only SQL statements only.
    """

    # Read-only operations. `EXPLAIN` and `SHOW` are not recognized as DML
    # by sqlparse, they are handled separately.
    permitted_operations = {"SELECT", "WITH"}

    # Write operations, which must not hide behind a read-only statement.
    # NB: Only keywords known to sqlparse can be matched here. Other statements,
    #     e.g. `OPTIMIZE`, `REFRESH`, or `KILL`, can not be nested into a query,
    #     and are denied by their leading token, see `operation`.
    mutation_keywords = {
        "ALTER",
        "ANALYZE",
        "COPY",
        "CREATE",
        "DELETE",
        "DROP",
        "GRANT",
        "INSERT",
        "REVOKE",
        "TRUNCATE",
        "UPDATE",
    }

    # `EXPLAIN [ANALYZE | VERBOSE] [(option [, ...])]`, leading the explained statement.
    explain_prefix = re.compile(
        r"^\s*EXPLAIN\b(\s+(ANALYZE|VERBOSE)\b)?(\s*\(\s*(ANALYZE|COSTS|VERBOSE)\b[^()]*\))?",
        flags=re.IGNORECASE,
    )

    expression: str
    permit_all: bool = False

    _parsed_sqlparse: t.Any = dataclasses.field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.expression is None:
            self.expression = ""
        if self.expression:
            self.expression = self.expression.strip()

    def parse_sqlparse(self) -> t.List[sqlparse.sql.Statement]:
        """
        Parse expression using traditional `sqlparse` library.
        """
        if self._parsed_sqlparse is None:
            self._parsed_sqlparse = sqlparse.parse(self.expression)
        return self._parsed_sqlparse

    @property
    def is_dql(self) -> bool:
        """
        Is it a DQL statement, which effectively invokes read-only operations only?
        """

        if not self.expression:
            return False

        if self.permit_all:
            return True

        # Reject evasive statements, e.g. `SELECT 42; DELETE FROM foobar`.
        if self.is_evasive:
            return False

        # `SHOW` is read-only by definition, e.g. `SHOW TABLES`, or `SHOW CREATE TABLE`.
        if self.operation == "SHOW":
            return True

        # `EXPLAIN` statements are only as read-only as the statement they explain.
        if self.operation == "EXPLAIN":
            explained = self.explained
            # Deny when the clause can not be stripped, e.g. when led by a comment.
            if explained.expression == self.expression:
                return False
            return explained.is_dql

        if self.operation not in self.permitted_operations:
            return False

        # Innocent-looking `SELECT`/`WITH` statements can still smuggle writes,
        # e.g. `SELECT ... INTO ...`, or `WITH x AS (DELETE FROM t) SELECT ...`.
        return not self.is_camouflage

    @property
    def explained(self) -> "SqlStatementClassifier":
        """
        The statement following `EXPLAIN`, without its options.

        Leading `EXPLAIN` clauses are stripped iteratively, to bound stack usage.
        """
        explained = self.expression
        while (stripped := self.explain_prefix.sub("", explained, count=1)) != explained:
            explained = stripped
        return SqlStatementClassifier(expression=explained)

    @property
    def operation(self) -> str:
        """
        The SQL operation: SELECT, INSERT, UPDATE, DELETE, CREATE, etc.
        """
        parsed = self.parse_sqlparse()
        operation = parsed[0].get_type().upper()
        if operation == "UNKNOWN":
            # Fall back to the leading token for statements sqlparse does not
            # classify, e.g. `EXPLAIN`, `SHOW`, or a parenthesized query.
            # NB: This must be the leading token, not the first keyword. sqlparse
            #     does not know each CrateDB statement, e.g. `OPTIMIZE` or `REFRESH`,
            #     which would otherwise be classified by a keyword following later.
            for token in parsed[0].flatten():
                if token.is_whitespace or token.ttype in Comment or token.value == "(":
                    continue
                return str(token.value).upper()
        return operation

    @property
    def mutation_keyword(self) -> t.Optional[str]:
        """
        The keyword of a write operation smuggled into a read-only statement, if any.
        """
        statement = self.parse_sqlparse()[0]
        for token in statement.flatten():
            if token.ttype in Keyword and token.value.upper() in self.mutation_keywords:
                return str(token.value).upper()
        return None

    @property
    def is_mutation(self) -> bool:
        """
        Whether a read-only statement smuggles in a write operation.
        """
        return self.mutation_keyword is not None

    @property
    def is_camouflage(self) -> bool:
        """
        Innocent-looking statements can evade filters.
        """
        return self.is_select_into or self.is_mutation

    @property
    def is_select_into(self) -> bool:
        """
        Use traditional `sqlparse` for catching `SELECT ... INTO ...` statements.
        Examples:
            SELECT * INTO foobar FROM bazqux
            SELECT * FROM bazqux INTO foobar
        """
        # Flatten all tokens (including nested ones) and match on type+value.
        statement = self.parse_sqlparse()[0]
        return any(
            token.ttype in Keyword and token.value.upper() == "INTO"
            for token in statement.flatten()
        )

    @property
    def is_evasive(self) -> bool:
        """
        Use traditional `sqlparse` for catching evasive SQL statements.

        A practice picked up from CodeRabbit was to reject multiple statements
        to prevent potential SQL injections. Is it a viable suggestion?

        Examples:

            SELECT * FROM users; \uff1b DROP TABLE users
        """
        parsed = self.parse_sqlparse()
        return len(parsed) > 1
