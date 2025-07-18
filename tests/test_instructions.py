from cratedb_mcp.__main__ import mcp


def test_instructions():
    instructions_text = mcp.instructions

    # MCP instructions.
    assert "MCP tool instructions" in instructions_text

    # General instructions.
    assert "Things to remember when working with CrateDB" in instructions_text
    assert "Rules for writing SQL queries" in instructions_text
    assert "Core writing principles" in instructions_text
