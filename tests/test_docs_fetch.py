import asyncio
import gzip
import itertools
import time
import zlib

import httpx
import pytest
from fastmcp import Client

from cratedb_mcp.core import CrateDbMcp
from cratedb_mcp.knowledge import MAX_PAGE_BYTES, MAX_REDIRECTS

INDEX_LINK = (
    "https://docs.cratedb.com/projects/crate-reference/en/latest/_sources/general/builtins/"
    "scalar-functions.rst.txt"
)
START = "https://docs.cratedb.com/projects/guide/start.html"
CHUNK = 65_536
TOO_LARGE = f"The page is larger than the {MAX_PAGE_BYTES:,} bytes the tool reads."


def fetch(link):
    async def call():
        async with Client(CrateDbMcp().mcp) as client:
            return await client.call_tool(
                "fetch_cratedb_docs", {"link": link}, raise_on_error=False
            )

    result = asyncio.run(call())
    return result.is_error, result.content[0].text


def moved(location, status=302):
    return lambda: httpx.Response(status, headers={"Location": location})


@pytest.mark.parametrize(
    "link",
    [
        "https://raw.githubusercontent.com/crate/crate/refs/heads/master/docs/general/builtins/scalar-functions.rst",
        "https://example.org/",
    ],
)
def test_link_outside_the_index_and_the_sites_is_refused_unrequested(docs_site, link):
    assert fetch(link) == (True, f"Link is not permitted: {link}")
    assert docs_site.requests == []


@pytest.mark.parametrize(
    "elsewhere",
    [
        "https://example.org/elsewhere?x=1",
        "http://docs.cratedb.com/projects/guide/final.html",
    ],
)
def test_redirect_to_an_address_that_is_not_fetched_fails_before_it_is_requested(
    docs_site, elsewhere
):
    docs_site.pages[START] = moved(elsewhere)
    docs_site.pages[elsewhere] = moved("https://docs.cratedb.com/projects/guide/final.html")
    assert fetch(START) == (True, "The page moved to an address the tool does not fetch.")
    assert docs_site.requests == [START]


def test_redirects_within_the_sites_and_to_index_links_are_followed(docs_site):
    old = "https://cratedb.com/docs/guide/start.html"
    nearby = "https://docs.cratedb.com/projects/guide/next.html"
    github_link = "https://raw.githubusercontent.com/crate/crate/refs/heads/master/README.rst"
    docs_site.pages[old] = moved(START, 301)
    docs_site.pages[START] = moved("/projects/guide/next.html", 308)
    docs_site.pages[nearby] = moved(github_link)
    assert fetch(old) == (False, docs_site.page)
    assert docs_site.requests == [old, START, nearby, github_link]


@pytest.mark.parametrize("steps", [MAX_REDIRECTS, MAX_REDIRECTS + 1])
def test_redirects_are_followed_up_to_the_limit(docs_site, steps):
    chain = [f"https://docs.cratedb.com/projects/guide/step-{n}.html" for n in range(steps + 1)]
    for here, there in itertools.pairwise(chain):
        docs_site.pages[here] = moved(there)
    if steps <= MAX_REDIRECTS:
        assert fetch(chain[0]) == (False, docs_site.page)
    else:
        assert fetch(chain[0]) == (True, f"The page redirects more than {MAX_REDIRECTS} times.")
    assert docs_site.requests == chain[: MAX_REDIRECTS + 1]


class Counted:
    """A body that counts how many of its bytes were read."""

    def __init__(self, chunks) -> None:
        self.chunks = chunks
        self.bytes_read = 0

    def __iter__(self):
        for chunk in self.chunks:
            self.bytes_read += len(chunk)
            yield chunk


def large_page():
    """A text page of 50 MiB."""
    return Counted(b"x" * CHUNK for _ in range(800))


def test_page_above_the_limit_is_refused_once_the_limit_is_read(docs_site):
    page = large_page()
    docs_site.pages[START] = lambda: httpx.Response(
        200, headers={"Content-Type": "text/plain"}, content=page
    )
    assert fetch(START) == (True, TOO_LARGE)
    assert MAX_PAGE_BYTES < page.bytes_read <= MAX_PAGE_BYTES + CHUNK


def test_page_announced_above_the_limit_is_refused_before_it_is_read(docs_site):
    page = large_page()
    headers = {"Content-Type": "text/plain", "Content-Length": str(50 * 1024 * 1024)}
    docs_site.pages[START] = lambda: httpx.Response(200, headers=headers, content=page)
    assert fetch(START) == (True, TOO_LARGE)
    assert page.bytes_read == 0


@pytest.mark.parametrize(("size", "refused"), [(MAX_PAGE_BYTES, False), (MAX_PAGE_BYTES + 1, True)])
def test_page_of_the_limit_is_fetched_and_a_larger_one_refused(docs_site, size, refused):
    docs_site.pages[START] = lambda: httpx.Response(200, text="x" * size)
    assert fetch(START)[0] is refused


@pytest.mark.parametrize(
    "content_type",
    ["application/pdf", "application/octet-stream", "image/png", "application/json", None],
)
def test_answer_that_is_not_text_is_refused(docs_site, content_type):
    headers = {"Content-Type": content_type} if content_type else {}
    docs_site.pages[START] = lambda: httpx.Response(200, content=b"%PDF-1.7", headers=headers)
    assert fetch(START) == (True, "The page is not text, so the tool does not return it.")


@pytest.mark.parametrize(
    "content_type", ["text/plain", "text/plain; charset=utf-8", "text/html", "Text/Markdown"]
)
def test_answer_that_is_text_is_returned(docs_site, content_type):
    docs_site.pages[START] = lambda: httpx.Response(
        200, content=b"# Title", headers={"Content-Type": content_type}
    )
    assert fetch(START) == (False, "# Title")


@pytest.mark.parametrize("fragment", ["", "#initcap"])
def test_index_link_is_fetched_with_or_without_a_fragment(docs_site, fragment):
    assert fetch(INDEX_LINK + fragment) == (False, docs_site.page)
    assert docs_site.requests == [INDEX_LINK]


@pytest.mark.parametrize(
    ("encoding", "body"),
    [
        ("gzip", gzip.compress(b"x" * MAX_PAGE_BYTES)),
        ("deflate", zlib.compress(b"x" * MAX_PAGE_BYTES)),
        ("gzip, gzip", gzip.compress(gzip.compress(b"x" * MAX_PAGE_BYTES))),
    ],
    ids=["gzip", "deflate", "gzip-twice"],
)
def test_compressed_answer_is_refused_before_it_is_read(docs_site, encoding, body):
    page = Counted([body])
    headers = {"Content-Type": "text/plain", "Content-Encoding": encoding}
    docs_site.pages[START] = lambda: httpx.Response(200, headers=headers, content=page)
    assert fetch(START) == (True, "The page is compressed, so the tool does not read it.")
    assert page.bytes_read == 0


@pytest.mark.parametrize("encoding", ["identity", "Identity", ""])
def test_answer_named_uncompressed_is_returned(docs_site, encoding):
    headers = {"Content-Type": "text/plain", "Content-Encoding": encoding}
    docs_site.pages[START] = lambda: httpx.Response(200, headers=headers, content=b"# Title")
    assert fetch(START) == (False, "# Title")


@pytest.mark.parametrize("charset", ["punycode", "x-unknown-to-python"])
def test_page_is_decoded_as_utf_8_whatever_charset_it_declares(docs_site, charset):
    text = "Größe – 大小 😀 " * 40_000
    headers = {"Content-Type": f"text/plain; charset={charset}"}
    body = text.encode() + b"\xff"
    docs_site.pages[START] = lambda: httpx.Response(200, headers=headers, content=body)
    started = time.monotonic()
    assert fetch(START) == (False, text + "\ufffd")
    assert time.monotonic() - started < 1


REASON = "Words of the site " + "z" * 60_000
UNREADABLE = "The site of the page sent an answer the tool cannot read."


def broken(error):
    def answer():
        raise error

    return answer


def broken_body():
    yield b"words of the site"
    raise httpx.ReadError("words of the site")


@pytest.mark.parametrize(
    ("answer", "message"),
    [
        (
            lambda: httpx.Response(
                500,
                content=b"words of the site",
                extensions={"reason_phrase": REASON.encode()},
            ),
            "The page answered HTTP 500.",
        ),
        (moved("https://docs.cratedb.com:words-of-the-site/"), UNREADABLE),
        (
            lambda: httpx.Response(
                200, headers={"Content-Type": "text/plain"}, content=broken_body()
            ),
            UNREADABLE,
        ),
        (broken(httpx.RemoteProtocolError("words of the site")), UNREADABLE),
        (broken(ValueError("words of the site")), UNREADABLE),
        (
            broken(httpx.ConnectError("words of the site")),
            "The site of the page cannot be reached.",
        ),
        (
            broken(httpx.ReadTimeout("words of the site")),
            "The page did not arrive within the 30-second timeout.",
        ),
    ],
    ids=[
        "status-with-reason-phrase",
        "location-with-invalid-port",
        "body-broken-off",
        "malformed-answer",
        "error-of-another-kind",
        "site-unreachable",
        "timeout",
    ],
)
def test_failure_is_said_in_a_sentence_that_holds_nothing_the_site_sent(docs_site, answer, message):
    docs_site.pages[START] = answer
    assert fetch(START) == (True, message)
