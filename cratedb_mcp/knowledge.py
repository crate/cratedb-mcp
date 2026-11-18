# ruff: noqa: E501
import logging
import threading
import typing as t

import cachetools
import httpx
from cratedb_about import CrateDbKnowledgeOutline
from fastmcp.exceptions import ToolError

from cratedb_mcp.settings import Settings

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
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

    # Sites whose pages are fetched besides the links of the documentation index.
    permitted_urls: t.List[str] = [
        "https://cratedb.com/",
        "https://docs.cratedb.com/",
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
        fetched from its site. The link, and the address of every redirect, is checked before
        it is requested.
        """
        if not self.url_permitted(link):
            raise ToolError(f"Link is not permitted: {link}")
        return self.download(httpx.URL(link).copy_with(fragment=None))

    @cachetools.cachedmethod(lambda self: self.pages, lock=lambda self: self.pages_lock)
    def download(self, url: httpx.URL) -> str:
        """
        Fetch the page at `url`, following its redirects, and keep its text for
        `CRATEDB_MCP_DOCS_CACHE_TTL` seconds. Every failure ends the call with a sentence of
        the tool's own, which holds nothing the site sent but the status code.
        """
        timeout = Settings.http_timeout()
        try:
            for _ in range(MAX_REDIRECTS + 1):
                page = read_page(url, timeout)
                if isinstance(page, str):
                    return page
                if not self.url_permitted(page):
                    logger.info("%s redirects to %s, which is not fetched", url, page)
                    raise ToolError("The page moved to an address the tool does not fetch.")
                url = page.copy_with(fragment=None)
        except ToolError:
            raise
        except httpx.TimeoutException as e:
            raise ToolError(
                f"The page did not arrive within the {timeout:g}-second timeout."
            ) from e
        except httpx.ConnectError as e:
            logger.info("Fetching %s failed: %r", url, e)
            raise ToolError("The site of the page cannot be reached.") from e
        except Exception as e:
            logger.info("Fetching %s failed: %r", url, e)
            raise ToolError("The site of the page sent an answer the tool cannot read.") from e
        raise ToolError(f"The page redirects more than {MAX_REDIRECTS} times.")

    @cachetools.cached(cache=cachetools.TTLCache(maxsize=1, ttl=settings.docs_cache_ttl() - 5))
    def items(self):
        """
        Return outline items, cached for a little bit less than one hour.
        """
        return self.outline.find_items().to_list()

    def url_permitted(self, url: t.Union[str, httpx.URL]) -> bool:
        """
        Whether a page is fetched: a link of the documentation index, or an https page under
        one of `permitted_urls`, on exactly its host and default port, without a user part.
        The fragment does not count, because it is never sent.
        """
        try:
            url = httpx.URL(url).copy_with(fragment=None)
        except httpx.InvalidURL:
            return False
        if any(httpx.URL(item["link"]).copy_with(fragment=None) == url for item in self.items()):
            return True
        return not url.userinfo and any(
            url.scheme == site.scheme
            and url.netloc == site.netloc
            and url.raw_path.startswith(site.raw_path)
            for site in map(httpx.URL, self.permitted_urls)
        )


documentation_client = httpx.Client()


def read_page(url: httpx.URL, timeout: float) -> t.Union[str, httpx.URL]:
    """
    Request `url` once, and return the text of the page, or the address it redirects to.
    A page has to be text.
    """
    with documentation_client.stream("GET", url, timeout=timeout) as response:
        if response.next_request is not None:
            return response.next_request.url
        check_page(response)
        body = response.read()
        return body.decode("utf-8", errors="replace")


def check_page(response: httpx.Response) -> None:
    """Fail unless `response` is a success that brings text."""
    if not response.is_success:
        raise ToolError(f"The page answered HTTP {response.status_code}.")
    if not response.headers.get("content-type", "").lower().startswith("text/"):
        raise ToolError("The page is not text, so the tool does not return it.")
