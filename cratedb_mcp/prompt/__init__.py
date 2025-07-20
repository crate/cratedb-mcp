import importlib.resources
import sys
from pathlib import Path
from typing import List, Optional

import httpx
from cratedb_about.prompt import GeneralInstructions


class InstructionsPrompt:
    """
    Bundle instructions how to use MCP tools with general instructions how to work with CrateDB.

    - MCP: https://github.com/crate/cratedb-examples/blob/7f1bc0f94d/topic/chatbot/table-augmented-generation/aws/cratedb_tag_inline_agent.ipynb?short_path=00988ad#L776-L794
    - General: https://github.com/crate/about
    """

    def __init__(self, instructions: Optional[str] = None, conventions: Optional[str] = None):
        fragments: List[str] = []
        if instructions:
            fragments.append(self.load_fragment(instructions))
        else:
            instructions_general = GeneralInstructions().render()
            mcp_instructions_file = (
                importlib.resources.files("cratedb_mcp.prompt") / "instructions.md"
            )
            if not mcp_instructions_file.is_file():  # pragma: no cover
                raise FileNotFoundError(f"MCP instructions file not found: {mcp_instructions_file}")
            instructions_mcp = mcp_instructions_file.read_text()
            fragments.append(instructions_general)
            fragments.append(instructions_mcp)
        if conventions:
            fragments.append(self.load_fragment(conventions))
        self.fragments = fragments

    def render(self) -> str:
        return "\n\n".join(map(str.strip, self.fragments))

    @staticmethod
    def load_fragment(fragment: str) -> str:
        """
        Load instruction fragment from various sources.

        Supports loading from:
        - HTTP(S) URLs
        - Local file paths
        - Standard input (when fragment is "-")
        - Direct string content

        That's a miniature variant of a "fragment" concept,
        adapted from `llm` [1] written by Simon Willison.

        [1] https://github.com/simonw/llm
        """
        try:
            if fragment.startswith("http://") or fragment.startswith("https://"):
                with httpx.Client(follow_redirects=True, max_redirects=3, timeout=5.0) as client:
                    response = client.get(fragment)
                    response.raise_for_status()
                    return response.text
            if fragment == "-":
                return sys.stdin.read()
            path = Path(fragment)
            if path.exists():
                return path.read_text(encoding="utf-8")
            return fragment
        except (httpx.HTTPError, OSError, UnicodeDecodeError) as e:
            raise ValueError(f"Failed to load fragment '{fragment}': {e}") from e
