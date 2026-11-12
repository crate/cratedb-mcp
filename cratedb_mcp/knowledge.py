# ruff: noqa: E501
import typing as t

import cachetools
from cratedb_about import CrateDbKnowledgeOutline
from cratedb_about.util import get_cache_client

from cratedb_mcp.settings import Settings


class Queries:
    SCHEMAS = """
SELECT table_schema,
       count(*) FILTER (WHERE table_type = 'BASE TABLE') AS tables,
       count(*) FILTER (WHERE table_type = 'VIEW') AS views
FROM information_schema.tables
{where}
GROUP BY table_schema
ORDER BY table_schema
    """
    TABLES = """
SELECT table_name, table_type
FROM information_schema.tables
WHERE table_schema = ? {pattern}
ORDER BY table_name
    """
    TABLE_TYPE = """
SELECT table_type
FROM information_schema.tables
WHERE table_schema = ? AND table_name = ?
    """
    VIEW_DEFINITION = """
SELECT view_definition
FROM information_schema.views
WHERE table_schema = ? AND table_name = ?
    """
    COLUMNS = """
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = ? AND table_name = ?
ORDER BY ordinal_position
    """
    TABLE_STORAGE = """
SELECT count(*) AS primary_shards,
       sum(num_docs) AS records,
       sum(size) AS size_bytes,
       count(DISTINCT partition_ident) FILTER (WHERE partition_ident <> '') AS partitions
FROM sys.shards
WHERE schema_name = ? AND table_name = ? AND "primary"
    """
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


class DocumentationIndex:
    """
    Define documentation sections supplied to the MCP server.
    Load knowledge outline from YAML file and read all items.

    The `description` attribute is very important, it gives context
    to the LLM to properly decide which one to use.

    Canonical source: https://github.com/crate/about/blob/main/src/cratedb_about/outline/cratedb-outline.yaml

    Examples:
    ```yaml
    - title: "CrateDB SQL functions"
      link: https://docs.cratedb.com/projects/crate-reference/en/latest/_sources/general/builtins/scalar-functions.rst.txt
      description: The reference documentation about all SQL functions CrateDB provides.

    - title: "Guide: CrateDB query optimization"
      link: https://docs.cratedb.com/projects/guide/_sources/performance/optimization.md.txt
      description: Essential principles for optimizing queries in CrateDB while avoiding the most common pitfalls.
    ```
    """

    settings = Settings()

    # List of permitted URL prefixes to acquire resources from on demand.
    permitted_urls: t.List[str] = [
        "https://cratedb.com/",
        "https://docs.cratedb.com/",
        "https://github.com/crate",
        "https://raw.githubusercontent.com/crate",
    ]

    def __init__(self):
        self.client = get_cache_client(ttl=self.settings.docs_cache_ttl())

        # Load documentation outline.
        self.outline = CrateDbKnowledgeOutline.load()

    @cachetools.cached(cache=cachetools.TTLCache(maxsize=1, ttl=settings.docs_cache_ttl() - 5))
    def items(self):
        """
        Return outline items, cached for a little bit less than one hour.
        """
        return self.outline.find_items().to_list()

    def url_permitted(self, url: str) -> bool:
        """
        Validate if a documentation URL is listed in the documentation index or is from a permitted domain.

        Only links from the documentation index, CrateDB domains, and specific GitHub repositories are allowed.

        Args:
            url: The URL to validate

        Returns:
            bool: True if the URL is permitted, False otherwise
        """
        if any(item["link"] == url for item in self.items()):
            return True
        for permitted_url in self.permitted_urls:
            if url.startswith(permitted_url):
                return True
        return False
