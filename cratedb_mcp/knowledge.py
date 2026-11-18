# ruff: noqa: E501
import threading
import typing as t

import cachetools
import httpx
from cratedb_about import CrateDbKnowledgeOutline

from cratedb_mcp.settings import Settings

CACHED_CHARS = 16_000_000


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
        self.pages: cachetools.TTLCache[httpx.URL, str] = cachetools.TTLCache(
            maxsize=CACHED_CHARS, ttl=Settings.docs_cache_ttl(), getsizeof=len
        )
        self.pages_lock = threading.Lock()

        # Load documentation outline.
        self.outline = CrateDbKnowledgeOutline.load()

    def fetch(self, link: str) -> str:
        """
        Return the text of the documentation page at `link`, kept from an earlier call or
        fetched from its site.
        """
        if not self.url_permitted(link):
            raise ValueError(f"Link is not permitted: {link}")
        return self.download(httpx.URL(link).copy_with(fragment=None))

    @cachetools.cachedmethod(lambda self: self.pages, lock=lambda self: self.pages_lock)
    def download(self, url: httpx.URL) -> str:
        """
        Fetch the page at `url`, following its redirects, and keep its text for
        `CRATEDB_MCP_DOCS_CACHE_TTL` seconds.
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


documentation_client = httpx.Client()
