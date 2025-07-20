import io

import pytest

from cratedb_mcp.__main__ import mcp
from cratedb_mcp.prompt import InstructionsPrompt


def test_default():
    """
    The default instructions are bundled from general and MCP-related instructions.
    """
    instructions_text = mcp.instructions

    # MCP instructions.
    assert "Tool instructions" in instructions_text

    # General instructions.
    assert "Things to remember when working with CrateDB" in instructions_text
    assert "Rules for writing SQL queries" in instructions_text
    assert "Core writing principles" in instructions_text


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
    assert "custom-convention" in prompt
    assert "Core writing principles" in prompt


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


def test_fragment_remote_success():
    """
    Verify fragments are loaded from HTTP URLs successfully.
    """
    instructions = InstructionsPrompt(instructions="https://www.example.org/")
    assert "Example Domain" in instructions.render()


def test_fragment_remote_failure():
    """
    Verify fragment-loading from HTTP URLs fails correctly.
    """
    with pytest.raises(ValueError) as ex:
        InstructionsPrompt(instructions="https://httpbin.org/404")
    assert ex.match(
        "Failed to load fragment 'https://httpbin.org/404': (Client error|Server error)"
    )
