import dataclasses
import logging
import typing as t

import sqlparse
from sqlparse.sql import Parenthesis

from cratedb_mcp.settings import Settings

logger = logging.getLogger(__name__)


def sql_is_permitted(expression: str) -> bool:
    """
    Validate the SQL expression, only permit read queries by default.

    When the `CRATEDB_MCP_PERMIT_ALL_STATEMENTS` environment variable is set,
    allow all types of statements. This is **not** recommended.
    """
    is_dql = SqlStatementClassifier(
        expression=expression, permit_all=Settings.permit_all_statements()
    ).is_dql
    if is_dql:
        logger.info(f"Permitted SQL expression: {expression and expression[:50]}...")
    else:
        logger.warning(f"Denied SQL expression: {expression and expression[:50]}...")
    return is_dql


@dataclasses.dataclass
class SqlStatementClassifier:
    """
    Helper to classify an SQL statement.

    Here, most importantly: Provide the `is_dql` property that signals
    truthfulness for a single `SELECT`, `WITH`, `VALUES` or `SHOW` statement,
    or an `EXPLAIN` of a `SELECT`, `WITH` or `VALUES` statement.
    """

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

        if self.is_evasive:
            return False

        if self.keyword == "EXPLAIN":
            explained = SqlStatementClassifier(self.explained)
            return explained.keyword not in ("EXPLAIN", "SHOW") and explained.is_dql

        return self.operation == "SELECT" or self.keyword in ("VALUES", "SHOW")

    @property
    def operation(self) -> str:
        """
        The SQL operation: SELECT, INSERT, UPDATE, DELETE, CREATE, etc.
        After a `WITH` clause, the operation that follows it.
        """
        parsed = self.parse_sqlparse()
        return parsed[0].get_type().upper()

    @property
    def keyword(self) -> str:
        """
        The first keyword of the statement, after comments.
        """
        parsed = self.parse_sqlparse()
        token = parsed[0].token_first(skip_cm=True) if parsed else None
        if token is None:
            return ""
        return next(token.flatten()).normalized.upper()

    @property
    def explained(self) -> str:
        """
        The statement an `EXPLAIN` statement explains, without its options.
        """
        statement = self.parse_sqlparse()[0]
        index = statement.token_index(statement.token_first(skip_cm=True))
        index, token = statement.token_next(index, skip_cm=True)
        while isinstance(token, Parenthesis) or (
            token is not None and token.normalized.upper() in ("ANALYZE", "VERBOSE")
        ):
            index, token = statement.token_next(index, skip_cm=True)
        if token is None:
            return ""
        return "".join(str(rest) for rest in statement.tokens[index:])

    @property
    def is_evasive(self) -> bool:
        """
        Whether the expression holds more than one statement.

        `sqlparse` reads a backslash in a string as an escape and CrateDB does
        not, so it may read one statement where CrateDB reads two. CrateDB runs
        one statement per request and refuses such a text.

        Examples:

            SELECT * FROM users; \uff1b DROP TABLE users
        """
        parsed = self.parse_sqlparse()
        return len(parsed) > 1
