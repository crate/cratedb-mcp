import asyncio
import importlib.resources
import io
import re

import httpx
import pytest
from fastmcp import Client

from cratedb_mcp.__main__ import mcp
from cratedb_mcp.core import CrateDbMcp
from cratedb_mcp.prompt import InstructionsPrompt

BUILTIN = (importlib.resources.files("cratedb_mcp.prompt") / "instructions.md").read_text().strip()


def test_default():
    """
    The default instructions are the text of the bundled file and nothing else.
    """
    assert mcp.instructions == BUILTIN


def test_default_names_registered_tools():
    """
    Every tool the default instructions name in backticks is registered by the server.
    """

    async def fetch():
        async with Client(CrateDbMcp().mcp) as client:
            return {tool.name for tool in await client.list_tools()}

    mentioned = set(re.findall(r"`([a-z]+(?:_[a-z]+)+)`", BUILTIN))
    assert mentioned
    assert mentioned <= asyncio.run(fetch())


def test_custom_instructions():
    """
    Verify custom instructions replace the built-in ones.
    """
    instructions = InstructionsPrompt(instructions="custom-instruction")
    assert instructions.render() == "custom-instruction"


def test_custom_conventions():
    """
    Verify custom conventions are added to the built-in ones.
    """
    instructions = InstructionsPrompt(conventions="custom-convention")
    prompt = instructions.render()
    assert prompt == f"{BUILTIN}\n\ncustom-convention"


def test_fragment_local(tmp_path):
    """
    Verify fragments are loaded from local filesystem.
    """
    tmp = tmp_path / "test.txt"
    tmp.write_text("custom-instruction")
    instructions = InstructionsPrompt(instructions=str(tmp))
    assert instructions.render() == "custom-instruction"


def test_fragment_stdin(mocker):
    """
    Verify fragments are loaded from STDIN.
    """
    mocker.patch("sys.stdin", io.StringIO("custom-instruction"))

    instructions = InstructionsPrompt(instructions="-")
    assert instructions.render() == "custom-instruction"


def serve(mocker, response):
    requests = []

    def answer(transport, request):
        requests.append(str(request.url))
        return response

    mocker.patch.object(httpx.HTTPTransport, "handle_request", answer)
    return requests


def test_fragment_remote_success(mocker):
    """
    Verify fragments are loaded from HTTP URLs successfully.
    """
    requests = serve(mocker, httpx.Response(200, text="custom-instruction"))
    instructions = InstructionsPrompt(instructions="https://example.org/instructions.md")
    assert instructions.render() == "custom-instruction"
    assert requests == ["https://example.org/instructions.md"]


def test_fragment_remote_failure(mocker):
    """
    Verify fragment-loading from HTTP URLs fails correctly.
    """
    serve(mocker, httpx.Response(404))
    with pytest.raises(ValueError) as ex:
        InstructionsPrompt(instructions="https://example.org/404")
    assert ex.match("Failed to load fragment 'https://example.org/404': Client error")
