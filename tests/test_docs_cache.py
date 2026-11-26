import asyncio
import os
import subprocess
import sys
import time

import pytest
from fastmcp import Client

from cratedb_mcp import tool
from cratedb_mcp.core import CrateDbMcp
from cratedb_mcp.knowledge import DocumentationIndex

LINK = "https://docs.cratedb.com/projects/crate-reference/en/latest/_sources/sql/page.rst.txt"


def text(link):
    async def call():
        async with Client(CrateDbMcp().mcp) as client:
            return await client.call_tool("fetch_cratedb_docs", {"link": link})

    return asyncio.run(call()).content[0].text


def test_a_page_is_fetched_again_once_its_lifetime_has_passed(docs_site, mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_DOCS_CACHE_TTL": "1"})
    mocker.patch.object(tool, "documentation_index", DocumentationIndex())
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


FETCH_A_PAGE = (
    "import httpx; "
    "httpx.HTTPTransport.handle_request = "
    "lambda self, request: httpx.Response(200, text='a page'); "
    "from cratedb_mcp.tool import fetch_cratedb_docs as f; "
    "assert f('https://docs.cratedb.com/projects/guide/') == 'a page'"
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
