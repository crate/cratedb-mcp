import typing as t

import httpx
import pytest

from cratedb_mcp import tool
from cratedb_mcp.knowledge import DocumentationIndex


class DocumentationSites:
    """
    Answer every request for a documentation page from memory: an address in `pages` with
    the response its function makes, any other address with the text `page`.
    """

    page = "initcap converts the first letter of each word to upper case"

    def __init__(self) -> None:
        self.pages: t.Dict[str, t.Callable[[], httpx.Response]] = {}
        self.requests: t.List[str] = []

    def answer(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(str(request.url))
        page = self.pages.get(str(request.url))
        if page is None:
            return httpx.Response(200, text=self.page)
        return page()


@pytest.fixture
def docs_site(mocker):
    """Serve documentation pages from memory, to a new index."""
    sites = DocumentationSites()
    mocker.patch.object(httpx.HTTPTransport, "handle_request", sites.answer)
    mocker.patch.object(tool, "documentation_index", DocumentationIndex())
    return sites


@pytest.fixture
def answer_with(mocker):
    """Answer every HTTP request with the response that `answer(request)` returns."""
    return lambda answer: mocker.patch.object(
        httpx.HTTPTransport, "handle_request", lambda _, request: answer(request)
    )
