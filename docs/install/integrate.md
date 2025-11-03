:::{include} ../_links.md
:::

(integrate)=

# Integrations

Integrate CrateDB MCP with standard AI applications.

## Claude, Cline, Cursor, Roo Code, Windsurf
Add the following configuration to your AI assistant's settings to enable the
CrateDB MCP Server.
- Claude: [`claude_desktop_config.json`](https://modelcontextprotocol.io/quickstart/user)
- Cline: [`cline_mcp_settings.json`](https://docs.cline.bot/mcp/configuring-mcp-servers)
- Cursor: [`~/.cursor/mcp.json` or `.cursor/mcp.json`](https://docs.cursor.com/context/model-context-protocol)
- Roo Code: [`mcp_settings.json` or `.roo/mcp.json`](https://docs.roocode.com/features/mcp/using-mcp-in-roo/)
- Windsurf: [`~/.codeium/windsurf/mcp_config.json`](https://docs.windsurf.com/windsurf/cascade/mcp)
```json
{
  "mcpServers": {
    "cratedb-mcp": {
      "command": "uvx",
      "args": ["cratedb-mcp", "serve"],
      "env": {
        "CRATEDB_CLUSTER_URL": "http://localhost:4200/",
        "CRATEDB_MCP_TRANSPORT": "stdio"
      },
      "alwaysAllow": [
        "get_cluster_health",
        "get_table_metadata",
        "query_sql",
        "get_cratedb_documentation_index",
        "fetch_cratedb_docs"
      ],
      "disabled": false
    }
  }
}
```

## VS Code
:::{div}
[Add an MCP server to your VS Code user settings] to enable the MCP server
across all workspaces in your `settings.json` file.
:::
```json
{
  "mcp": {
    "servers": {
      "cratedb-mcp": {
        "command": "uvx",
        "args": ["cratedb-mcp", "serve"],
        "env": {
          "CRATEDB_CLUSTER_URL": "http://localhost:4200/",
          "CRATEDB_MCP_TRANSPORT": "stdio"
        }
      }
    }
  },
  "chat.mcp.enabled": true
}
```
:::{div}
[Add an MCP server to your VS Code workspace] to configure an MCP server for a
specific workspace per `.vscode/mcp.json` file. In this case, omit the
top-level `mcp` element, and start from `servers` instead.

Alternatively, VS Code can automatically detect and reuse MCP servers that
you defined in other tools, such as Claude Desktop.
See also [Automatic discovery of MCP servers].
:::
```json
{
  "chat.mcp.discovery.enabled": true
}
```

## Goose
:::{div}
Configure `extensions` in your `~/.config/goose/config.yaml`.
See also [using Goose extensions].
:::
```yaml
extensions:
  cratedb-mcp:
    name: CrateDB MCP
    type: stdio
    cmd: uvx
    args:
      - cratedb-mcp
      - serve
    enabled: true
    envs:
      CRATEDB_CLUSTER_URL: "http://localhost:4200/"
      CRATEDB_MCP_TRANSPORT: "stdio"
    timeout: 300
```

## LibreChat
:::{div}
Configure `mcpServers` in your `librechat.yaml`.
See also [LibreChat and MCP] and [LibreChat MCP examples].
:::
```yaml
mcpServers:
  cratedb-mcp:
    type: stdio
    command: uvx
    args:
      - cratedb-mcp
      - serve
    env:
      CRATEDB_CLUSTER_URL: "http://localhost:4200/"
      CRATEDB_MCP_TRANSPORT: "stdio"
```

## OCI
If you prefer to deploy the MCP server using Docker or Podman, your command/args
configuration snippet may look like this.
```json
{
  "mcpServers": {
    "cratedb-mcp": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "-e", "CRATEDB_CLUSTER_URL",
        "ghcr.io/crate/cratedb-mcp:latest"
      ],
      "env": {
        "CRATEDB_CLUSTER_URL": "http://cratedb.example.org:4200/",
        "CRATEDB_MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```
