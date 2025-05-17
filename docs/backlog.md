# CrateDB MCP backlog

## Iteration +1
- README: Provide guidelines on how to create a CrateDB read-only user
- CLI: Honor `--read-only` option flag
  - https://fluxcd.control-plane.io/mcp/config/
- mcptools: `mcpt call` does not exit with returncode != 0 when "Unknown tool:" happens
- Release v0.0.1

## Iteration +2
- Migrate to FastAPI 2.0
  - https://gofastmcp.com/getting-started/welcome#fastmcp-2-0-and-the-official-mcp-sdk
  - https://gofastmcp.com/patterns/testing
- Install: Others also just use `docker` right away? Others discourage using `uvx`.
  - https://github.com/ppl-ai/modelcontextprotocol/?tab=readme-ov-file#step-3-configure-claude-desktop
  - https://medium.com/@scalablecto/stop-running-your-mcp-tools-via-npx-uvx-right-now-380d1ab99d3f
- Ecosystem: Link to 3rd-party installation instructions?
  - https://code.visualstudio.com/docs/copilot/chat/mcp-servers#_add-an-mcp-server-to-your-workspace
  - https://docs.cline.bot/mcp/configuring-mcp-servers
  - https://docs.cline.bot/mcp/adding-mcp-servers-from-github
  - https://docs.cline.bot/mcp/connecting-to-a-remote-server
- Ecosystem: Server Composition
  - https://gofastmcp.com/servers/fastmcp#composing-servers
  - https://gofastmcp.com/servers/composition
  - https://github.com/f/mcptools/pull/41

## Iteration +3
- Provide "instructions"
  > For the best experience with the CrateDB MCP Server, it’s crucial to provide your
  > AI assistant with proper instructions on how to interact. [...] The CrateDB MCP Server
  > comes with a set of predefined instructions that you can copy from the `instructions.md` file.

  Blueprint:
    - https://fluxcd.io/blog/2025/05/ai-assisted-gitops/
    - https://fluxcd.control-plane.io/mcp/prompt-engineering/
    - https://raw.githubusercontent.com/controlplaneio-fluxcd/distribution/refs/heads/main/docs/mcp/instructions.md
- Docs: Load documentation index from a custom outline file
- Naming things: Better names for API entrypoints?
- Use `platformdirs.user_cache_dir` for Hishel, see `pueblo.cache`
- Refactoring
  - Extract `SqlFilter` or `SqlGateway` functionality to the `cratedb-sqlparse` package
  - Extract other utilities to the `pueblo` package

## Done
- Make it work
- SQL: Stronger read-only mode
- Docs: HTTP caching
- Improve documentation
- Format code, improve linting
- Docs: About `CRATEDB_MCP_HTTP_TIMEOUT`
- Release v0.0.0
- CLI: For real. Blueprint: https://fluxcd.control-plane.io/mcp/config/
- Enable MCP transport `streamable-http`
- UX: Make `streamable-http` the default transport? => No.
- Docs:
  > Claude, Cursor, and Windsurf vs. VS Code Copilot Chat
  > -- https://fluxcd.control-plane.io/mcp/install/#configuration-with-ai-assistants
- Docs:
  > Once installed, you can configure your AI assistant to use the Flux MCP Server. 
  > For Claude, Cursor, Windsurf, or GitHub Copilot add the following configuration
  > to the MCP settings.
  > -- https://fluxcd.io/blog/2025/05/ai-assisted-gitops/#getting-started
- Docs: Improve README. The Flux MCP Server and Operator are excellent blueprints.
  https://github.com/controlplaneio-fluxcd/flux-operator
  https://fluxcd.control-plane.io/mcp/
- UX: Improve documentation, generalizing a bit beyond Claude only
- README: Use FastMCP client instead of `mcptools` program? => No. There is no FastMCP client.
- README: What's inside: Talk about "MCP tools"
