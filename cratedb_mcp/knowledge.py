# ruff: noqa: E501
import sqlite3
import threading
import time
import typing as t
import warnings
from pathlib import Path

import hishel
import httpx
from cratedb_about import CrateDbKnowledgeOutline

from cratedb_mcp.settings import Settings


class Queries:
    TABLES_COLUMNS = """
SELECT
    c.table_schema,
    c.table_name,
    c.column_name,
    c.data_type,
    c.is_nullable,
    c.column_default
FROM information_schema.columns c
WHERE {where}
ORDER BY
    c.table_schema,
    c.table_name,
    c.ordinal_position
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
      link: https://cratedb.com/docs/crate/reference/en/latest/_sources/general/builtins/scalar-functions.rst.txt
      description: The reference documentation about all SQL functions CrateDB provides.

    - title: "Guide: CrateDB query optimization"
      link: https://cratedb.com/docs/guide/_sources/performance/optimization.rst.txt
      description: Essential principles for optimizing queries in CrateDB while avoiding the most common pitfalls.
    ```
    """

    settings = Settings()

    # List of permitted URL prefixes to acquire resources from on demand.
    permitted_urls: t.List[str] = [
        "https://cratedb.com/",
        "https://github.com/crate/",
        "https://raw.githubusercontent.com/crate/",
    ]

    def __init__(self) -> None:
        # Load documentation outline.
        self.outline = CrateDbKnowledgeOutline.load()

        # Links of the curated index are permitted verbatim. The index advertises
        # a few resources outside the permitted URL prefixes, e.g. documentation
        # of PostgreSQL drivers, which could not be fetched otherwise. Matching
        # them exactly keeps the allowlist tight, no further prefixes are opened.
        self._indexed_links: t.FrozenSet[str] = frozenset(
            item.link for item in self.outline.find_items()
        )

        # Defer creating the HTTP client, it may touch the file system.
        # Tools run in a thread pool, so creating it is guarded by a lock.
        self._client: t.Optional[httpx.Client] = None
        self._client_lock = threading.Lock()

        # Outline items, cached according to the lifetime configured at access time.
        self._items: t.Optional[list] = None
        self._items_expiry: float = 0.0

    @property
    def client(self) -> httpx.Client:
        """
        Return the HTTP client to acquire documentation resources with, using a cache.
        """
        with self._client_lock:
            if self._client is None:
                self._client = self._make_client()
            return self._client

    def disable_cache(self, reason: Exception) -> None:
        """
        Carry on with an uncached HTTP client, after the cache failed while serving a request.
        """
        warnings.warn(
            f"Documentation cache failed: {reason}. Falling back to an uncached HTTP client.",
            category=UserWarning,
            stacklevel=2,
        )
        with self._client_lock:
            if self._client is not None:
                self._client.close()
            self._client = httpx.Client()

    def _make_client(self) -> httpx.Client:
        """
        Build the HTTP client to acquire documentation resources with.

        Falls back to an uncached client when caching is disabled, or when the
        cache is unavailable, e.g. on a read-only file system.
        """
        ttl = self.settings.docs_cache_ttl()
        if ttl <= 0:
            return httpx.Client()
        cache_path = Path(self.settings.docs_cache_dir()) / "documentation.sqlite"
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            # Tools run in a thread pool, so the connection must be shareable.
            connection = sqlite3.connect(cache_path, check_same_thread=False)
            storage = hishel.SQLiteStorage(connection=connection, ttl=ttl)
            controller = hishel.Controller(allow_stale=True)
            return hishel.CacheClient(controller=controller, storage=storage)
        except Exception as e:
            # The cache is optional, so any failure to set it up must not break the tool.
            warnings.warn(
                f"Cannot use documentation cache at `{cache_path}`: {e}. "
                f"Falling back to an uncached HTTP client.",
                category=UserWarning,
                stacklevel=2,
            )
            return httpx.Client()

    def items(self):
        """
        Return outline items, cached for a little bit less than the configured cache lifetime.
        """
        now = time.monotonic()
        if self._items is None or now >= self._items_expiry:
            self._items = self.outline.find_items().to_list()
            self._items_expiry = now + max(self.settings.docs_cache_ttl() - 5, 0)
        return self._items

    def url_permitted(self, url: str) -> bool:
        """
        Validate if a documentation URL is permitted to be fetched.

        Only links of the curated documentation index, and URLs from CrateDB
        domains and specific GitHub repositories are allowed.

        Args:
            url: The URL to validate

        Returns:
            bool: True if the URL is permitted, False otherwise
        """
        if url in self._indexed_links:
            return True
        for permitted_url in self.permitted_urls:
            if url.startswith(permitted_url):
                return True
        return False
