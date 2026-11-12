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
    STATS = """
SELECT settings['stats']['enabled'], settings['stats']['jobs_log_size'], CURRENT_USER
FROM sys.cluster
    """
    JOBS_LOG = """
SELECT date_format(ended) AS ended,
       CAST(ended AS BIGINT) - CAST(started AS BIGINT) AS duration_ms,
       username, substr(stmt, 1, ?) AS stmt, error IS NOT NULL AS failed
FROM sys.jobs_log
WHERE {where}
ORDER BY {order} DESC
LIMIT ?
    """
    JOBS = """
SELECT date_format(started) AS started,
       CAST(CURRENT_TIMESTAMP AS BIGINT) - CAST(started AS BIGINT) AS running_ms,
       username, substr(stmt, 1, ?) AS stmt
FROM sys.jobs
WHERE stmt ~ ? AND stmt <> ?
ORDER BY started
LIMIT ?
    """
    JOBS_METRICS = """
SELECT node['name'] AS node, classification['type'] AS type,
       classification['labels'] AS labels, total_count AS statements, failed_count AS failed,
       sum_of_durations AS total_ms, percentiles['50'] AS p50_ms, percentiles['90'] AS p90_ms,
       percentiles['99'] AS p99_ms, max AS max_ms
FROM sys.jobs_metrics
ORDER BY sum_of_durations DESC
LIMIT ?
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
