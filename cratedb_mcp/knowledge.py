# ruff: noqa: E501
import logging

import sqlparse

from cratedb_mcp.settings import PERMIT_ALL_STATEMENTS

logger = logging.getLogger(__name__)


class Queries:
    TABLES_METADATA = """
WITH partitions_health AS (SELECT table_name,
                                      table_schema,
                                      SUM(underreplicated_shards)                              as total_underreplicated_shards,
                                      SUM(missing_shards)                                      as total_missing_shards,
                                      ARRAY_AGG(
                                        {
              "health" = health, "missing_shards" = missing_shards,
                                 "partition_ident" = partition_ident,
                                 "severity" = severity,
                                 "underreplicated_shards" = underreplicated_shards }
          ) AS partitions_health,
                                      CASE
                                        WHEN 'RED' = ANY(ARRAY_AGG(health)) then 'RED'
                                        WHEN 'YELLOW' = ANY(ARRAY_AGG(health)) then 'YELLOW'
                                        ELSE 'GREEN' END                                       AS overall_health
                               FROM sys.health
                               GROUP BY table_name,
                                        table_schema),
         shards AS (SELECT table_name,
                           schema_name                   as table_schema,
                           SUM(num_docs)                 as total_records,
                           SUM(size)                     as total_size_bytes,
                           ARRAY_AGG(
                             {
              "id" = id, "partition_ident" = partition_ident,
                         "records" = num_docs,
                         "size_bytes" = size,
                         "primary" = primary }
          ) as shards
                    FROM sys.shards
                    WHERE
                      primary = TRUE
                    GROUP BY
                      table_name,
                      schema_name)
    SELECT inf.table_schema,
           ARRAY_AGG(
             {
            "table_name" = inf.table_name, "table_schema" = inf.table_schema,
                                           "replicas" = inf.number_of_replicas,
                                           "shards" = sha.shards,
                                           "partitions_health" = he.partitions_health,
                                           "overall_health" = he.overall_health,
                                           "total_records" = sha.total_records,
                                           "total_size_bytes" = sha.total_size_bytes,
                                           "total_missing_shards" = he.total_missing_shards,
                                           "total_underreplicated_shards" =
                                           he.total_underreplicated_shards,
                                           "table_type" = inf.table_type,
                                           "partitioned_by" = inf.partitioned_by,
                                           "clustered_by" = inf.clustered_by,
                                           "version" = inf.version }
        ) AS tables
    FROM information_schema.tables inf
           LEFT JOIN partitions_health he ON inf.table_name = he.table_name
      and inf.table_schema = he.table_schema
           LEFT JOIN shards sha ON inf.table_name = sha.table_name
      AND inf.table_schema = sha.table_schema
    GROUP BY inf.table_schema
    ORDER BY CASE
               WHEN table_schema IN ('doc') THEN 0
               WHEN table_schema IN (
                                     'sys',
                                     'information_schema',
                                     'pg_catalog',
                                     'blob'
                 ) THEN 2
               ELSE 1 END,
             table_schema;
"""
    HEALTH = """SELECT health,
           missing_shards,
           partition_ident,
           severity,
           table_name,
           table_schema,
           underreplicated_shards
    FROM sys.health
    ORDER BY severity DESC"""


# 'description' is very important, it gives context to the LLMs to properly decide which one to use.
DOCUMENTATION_INDEX = [
    # TODO: Add all there are.
    {
        "name": "about/overview",
        "description": "The most important factual and technical information about CrateDB per medium-sized (~300kB) llms.txt context file.",
        "link": "https://cdn.crate.io/about/v1/llms.txt"},
    {
        "name": "scalar functions",
        "description": "documentation about specific scalar/methods/functions for CrateDB SQL",
        "link": "https://raw.githubusercontent.com/crate/crate/refs/heads/5.10/docs/general/builtins/scalar-functions.rst"},
    {
        "name": "optimize query 101",
        "description": "documentation about optimizing CrateDB SQL statements",
        "link": "https://raw.githubusercontent.com/crate/cratedb-guide/9ab661997d7704ecbb63af9c3ee33535957e24e6/docs/performance/optimization.rst"
    }
]


def sql_expression_permitted(expression: str) -> bool:
    """
    Validate the SQL expression, only permit read queries by default.

    When the `CRATEDB_MCP_PERMIT_ALL_STATEMENTS` environment variable is set,
    allow all types of statements.

    FIXME: Revisit implementation, it might be too naive or weak.
           Issue:    https://github.com/crate/cratedb-mcp/issues/10
           Question: Does SQLAlchemy provide a solid read-only mode, or any other library?
    """
    outcome = _sql_expression_permitted(expression)
    if outcome is True:
        logger.info(f"Permitted SQL expression: {expression}")
    else:
        logger.warning(f"Denied SQL expression: {expression}")
    return outcome


def _sql_expression_permitted(expression: str) -> bool:

    if not expression:
        return False

    if PERMIT_ALL_STATEMENTS:
        return True

    # Parse the SQL statement.
    parsed = sqlparse.parse(expression.strip())
    if not parsed:
        return False

    # Check for multiple statements (potential SQL injection).
    if len(parsed) > 1:
        return False

    # Check if the expression is valid and if it's a SELECT statement,
    # also trying to consider `SELECT ... INTO ...` statements.
    operation = parsed[0].get_type().upper()
    tokens = [str(item).upper() for item in parsed[0]]
    if operation != 'SELECT' or (operation == 'SELECT' and 'INTO' in tokens):
        return False
    return True
