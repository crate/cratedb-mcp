# ruff: noqa: E501
import collections
import sys
import threading
import time
import typing as t

import cachetools
import httpx
from cratedb_about import CrateDbKnowledgeOutline

from cratedb_mcp.settings import Settings
from cratedb_mcp.util.http_client import shared_client

CACHED_PAGES = 200
CACHED_BYTES = 16_000_000


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
        self.pages = PageCache()

        # Load documentation outline.
        self.outline = CrateDbKnowledgeOutline.load()

    def fetch(self, link: str) -> str:
        """
        Return the text of the documentation page at `link`, kept from an earlier call or
        fetched from its site.
        """
        if not self.url_permitted(link):
            raise ValueError(f"Link is not permitted: {link}")
        address = str(httpx.URL(link).copy_with(fragment=None))
        text = self.pages.get(address)
        if text is None:
            text = self.download(httpx.URL(address))
            self.pages.put(address, text)
        return text

    def download(self, url: httpx.URL) -> str:
        """
        Fetch the page at `url`, following its redirects to a permitted address.
        """
        response = documentation_client.get(
            url, timeout=Settings.http_timeout(), follow_redirects=True
        )
        if not self.url_permitted(str(response.url)):
            raise ValueError(f"Link redirects to a location that is not permitted: {response.url}")
        response.raise_for_status()
        return response.text

    @cachetools.cached(cache=cachetools.TTLCache(maxsize=1, ttl=settings.docs_cache_ttl() - 5))
    def items(self):
        """
        Return outline items, cached for a little bit less than one hour.
        """
        return self.outline.find_items().to_list()

    def url_permitted(self, url: str) -> bool:
        """
        Validate if a documentation URL is from a permitted domain.

        Only URLs from CrateDB domains and specific GitHub repositories are allowed.

        Args:
            url: The URL to validate

        Returns:
            bool: True if the URL is from a permitted domain, False otherwise
        """
        for permitted_url in self.permitted_urls:
            if url.startswith(permitted_url):
                return True
        return False


class PageCache:
    """
    The text of fetched pages by address, each served for `CRATEDB_MCP_DOCS_CACHE_TTL`
    seconds after it was fetched. Beyond CACHED_PAGES pages, or CACHED_BYTES bytes of
    addresses and text in memory, the page read least recently goes.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pages: t.OrderedDict[str, t.Tuple[float, str]] = collections.OrderedDict()
        self._bytes = 0

    def get(self, address: str) -> t.Optional[str]:
        with self._lock:
            if address not in self._pages:
                return None
            expires, text = self._pages[address]
            if time.monotonic() >= expires:
                self._drop(address)
                return None
            self._pages.move_to_end(address)
            return text

    def put(self, address: str, text: str) -> None:
        expires = time.monotonic() + Settings.docs_cache_ttl()
        with self._lock:
            if address in self._pages:
                self._drop(address)
            self._pages[address] = (expires, text)
            self._bytes += sys.getsizeof(address) + sys.getsizeof(text)
            while len(self._pages) > CACHED_PAGES or self._bytes > CACHED_BYTES:
                self._drop(next(iter(self._pages)))

    def _drop(self, address: str) -> None:
        _, text = self._pages.pop(address)
        self._bytes -= sys.getsizeof(address) + sys.getsizeof(text)


documentation_client = shared_client(limits=httpx.Limits(max_keepalive_connections=0))
