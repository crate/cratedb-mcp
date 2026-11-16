import asyncio
import os
import subprocess
import sys
import threading
import time

import httpx
import pytest
from fastmcp import Client

from cratedb_mcp import knowledge
from cratedb_mcp.core import CrateDbMcp

LINK = "https://docs.cratedb.com/projects/crate-reference/en/latest/_sources/sql/page.rst.txt"
GUIDE = "https://docs.cratedb.com/projects/guide/"


def read(link, start=None):
    arguments = {"link": link} if start is None else {"link": link, "start": start}

    async def call():
        async with Client(CrateDbMcp().mcp) as client:
            return await client.call_tool("fetch_cratedb_docs", arguments, raise_on_error=False)

    return asyncio.run(call())


def text(link):
    result = read(link)
    return result.content[0].text if result.is_error else result.structured_content["text"]


def test_a_long_page_is_read_in_parts_from_one_fetch(docs_site, mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": "40"})
    page = docs_site.page
    first = read(LINK).structured_content
    assert first == {
        "text": page[:38],
        "truncated": True,
        "note": "Only characters 0 to 38 of 60 are shown, to keep the answer under the limit. "
        "Call again with start=38 to read on.",
    }
    assert read(LINK, start=38).structured_content == {"text": page[38:], "truncated": False}
    assert docs_site.requests == [LINK]


def test_a_start_past_the_end_of_the_page_fails(docs_site):
    result = read(LINK, start=60)
    assert result.is_error is True
    assert result.content[0].text == "The page holds 60 characters, so `start` must be lower."


def test_a_cap_without_room_for_any_text_says_so(docs_site, mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": "2"})
    assert read(LINK).structured_content == {
        "text": "",
        "truncated": True,
        "note": "No text is shown, because the cap of 2 characters leaves no room for it.",
    }


def test_a_page_is_fetched_again_once_its_lifetime_has_passed(docs_site, mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_DOCS_CACHE_TTL": "1"})
    assert text(LINK) == docs_site.page
    assert text(LINK) == docs_site.page
    assert docs_site.requests == [LINK]
    time.sleep(1.1)
    assert text(LINK) == docs_site.page
    assert text(LINK) == docs_site.page
    assert docs_site.requests == [LINK, LINK]


def test_an_address_with_another_fragment_shares_the_page_and_another_query_does_not(docs_site):
    for link in [LINK, LINK + "#section", LINK + "?q=x", LINK + "?q=x#section"]:
        assert text(link) == docs_site.page
    assert docs_site.requests == [LINK, LINK + "?q=x"]


@pytest.mark.parametrize(
    "answer",
    [
        lambda: httpx.Response(404),
        lambda: httpx.Response(
            200, headers={"Content-Type": "text/plain"}, content=iter([b"x" * 600_000] * 2)
        ),
    ],
    ids=["failed", "cut-off"],
)
def test_a_failed_or_cut_off_fetch_keeps_nothing(docs_site, answer):
    docs_site.pages[LINK] = answer
    assert read(LINK).is_error is True
    del docs_site.pages[LINK]
    assert text(LINK) == docs_site.page
    assert text(LINK) == docs_site.page
    assert docs_site.requests == [LINK, LINK]


@pytest.mark.parametrize(
    ("bound", "suffix"),
    [("CACHED_PAGES", ""), ("CACHED_BYTES", ""), ("CACHED_BYTES", "?q=" + "a" * 60_000)],
    ids=["pages", "bytes", "bytes-at-long-addresses"],
)
def test_beyond_a_bound_the_page_read_least_recently_goes(docs_site, mocker, bound, suffix):
    a, b, c = (GUIDE + letter + suffix for letter in "abc")
    two_pages = 2
    if bound == "CACHED_BYTES":
        two_pages *= sys.getsizeof(a) + sys.getsizeof(docs_site.page)
    mocker.patch.object(knowledge, bound, two_pages)
    for link in [a, b, a, c, a, b]:
        assert text(link) == docs_site.page
    assert docs_site.requests == [a, b, c, b]


def test_forty_calls_at_once_get_their_pages(docs_site):
    links = [f"{GUIDE}page-{n % 10}.html" for n in range(40)]

    def slowly(link):
        def answer():
            time.sleep(0.05)
            return httpx.Response(200, text=link)

        return answer

    for link in set(links):
        docs_site.pages[link] = slowly(link)

    async def call_all():
        async with Client(CrateDbMcp().mcp) as client:
            calls = [client.call_tool("fetch_cratedb_docs", {"link": link}) for link in links]
            return [result.structured_content["text"] for result in await asyncio.gather(*calls)]

    assert asyncio.run(call_all()) == links
    fetched = len(docs_site.requests)
    assert asyncio.run(call_all()) == links
    assert len(docs_site.requests) == fetched


def test_a_kept_page_is_served_while_another_page_is_fetched(docs_site):
    slow = GUIDE + "slow.html"
    released = threading.Event()

    def when_released():
        released.wait(5)
        return httpx.Response(200, text="slow")

    docs_site.pages[slow] = when_released
    assert text(LINK) == docs_site.page

    async def scenario():
        async with Client(CrateDbMcp().mcp) as client:
            pending = asyncio.create_task(client.call_tool("fetch_cratedb_docs", {"link": slow}))
            await asyncio.sleep(0.2)
            started = time.monotonic()
            kept = await client.call_tool("fetch_cratedb_docs", {"link": LINK})
            took = time.monotonic() - started
            released.set()
            await pending
            return kept.structured_content["text"], took

    kept, took = asyncio.run(scenario())
    assert kept == docs_site.page
    assert took < 1
    assert docs_site.requests == [LINK, slow]


FETCH_A_PAGE = (
    "import httpx; "
    "httpx.HTTPTransport.handle_request = "
    "lambda self, request: httpx.Response(200, text='a page'); "
    "from cratedb_mcp.tool import fetch_cratedb_docs as f; "
    "assert f('https://docs.cratedb.com/projects/guide/').text == 'a page'"
)


def run_python(code, home):
    env = {"HOME": str(home), "PATH": ""}
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=False
    )


@pytest.mark.parametrize(
    "code",
    [
        "from cratedb_mcp.cli import cli; cli(['--help'])",
        "from cratedb_mcp.cli import cli; cli(['show-prompt'])",
        "from cratedb_mcp.tool import get_cratedb_documentation_index as f; assert f()",
        FETCH_A_PAGE,
    ],
    ids=["help", "show-prompt", "documentation-index", "documentation-page"],
)
def test_server_code_runs_when_the_home_folder_cannot_be_written(tmp_path, code):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file where a folder belongs")
    result = run_python(code, blocker)
    assert result.returncode == 0, result.stderr


def test_fetching_a_page_writes_nothing_to_the_home_folder(tmp_path):
    result = run_python(FETCH_A_PAGE, tmp_path)
    assert result.returncode == 0, result.stderr
    assert list(tmp_path.iterdir()) == []
