# ruff: noqa: E501
import collections
import logging
import sys
import threading
import time
import typing as t

import cachetools
import httpx
from cratedb_about import CrateDbKnowledgeOutline
from fastmcp.exceptions import ToolError

from cratedb_mcp.settings import Settings
from cratedb_mcp.util.http_client import abandoned_from_connect, shared_client

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
MAX_PAGE_BYTES = 1_000_000
TOO_LARGE = f"The page is larger than the {MAX_PAGE_BYTES:,} bytes the tool reads."
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

    # Sites whose pages are fetched besides the links of the documentation index.
    permitted_urls: t.List[str] = [
        "https://cratedb.com/",
        "https://docs.cratedb.com/",
    ]

    def __init__(self):
        self.pages = PageCache()

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
        address = str(httpx.URL(link).copy_with(fragment=None))
        text = self.pages.get(address)
        if text is None:
            text = self.download(httpx.URL(address))
            self.pages.put(address, text)
        return text

    def download(self, url: httpx.URL) -> str:
        """
        Fetch the page at `url`, following its redirects, within one HTTP timeout once
        connected. Every failure ends the call with a sentence of the tool's own, which holds
        nothing the site sent but the status code.
        """
        timeout = Settings.http_timeout()
        deadline = time.monotonic() + timeout
        try:
            for _ in range(MAX_REDIRECTS + 1):
                page = read_page(url, deadline)
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


# Each request opens its own connection, so that its deadline watches it from the connect on.
documentation_client = shared_client(limits=httpx.Limits(max_keepalive_connections=0))


def read_page(url: httpx.URL, deadline: float) -> t.Union[str, httpx.URL]:
    """
    Request `url` once, and return the text of the page, or the address it redirects to.
    A page has to be uncompressed text of at most MAX_PAGE_BYTES that arrives by `deadline`.
    """
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise httpx.ConnectTimeout("The deadline passed before the request.")
    with abandoned_from_connect(deadline) as (trace, abandoned):
        try:
            with documentation_client.stream(
                "GET", url, timeout=remaining, extensions={"trace": trace}
            ) as response:
                if response.next_request is not None:
                    return response.next_request.url
                check_page(response)
                body = bytearray()
                for chunk in response.iter_bytes():
                    body += chunk
                    if len(body) > MAX_PAGE_BYTES:
                        raise ToolError(TOO_LARGE)
                    if time.monotonic() > deadline:
                        break
                else:
                    return body.decode("utf-8", errors="replace")
        except httpx.TransportError:
            if not abandoned.is_set():
                raise
    raise httpx.ReadTimeout("The page was still arriving at the deadline.")


def check_page(response: httpx.Response) -> None:
    """
    Fail unless `response` is a success that brings uncompressed text, and announces no more
    than MAX_PAGE_BYTES.
    """
    if not response.is_success:
        raise ToolError(f"The page answered HTTP {response.status_code}.")
    if not response.headers.get("content-type", "").lower().startswith("text/"):
        raise ToolError("The page is not text, so the tool does not return it.")
    encodings = response.headers.get_list("content-encoding", split_commas=True)
    if any(encoding.strip().lower() not in ("", "identity") for encoding in encodings):
        raise ToolError("The page is compressed, so the tool does not read it.")
    if int(response.headers.get("content-length") or 0) > MAX_PAGE_BYTES:
        raise ToolError(TOO_LARGE)
