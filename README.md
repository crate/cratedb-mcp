# CrateDB MCP Server

[![Status][badge-status]][project-pypi]
[![CI][badge-ci]][project-ci]
[![Coverage][badge-coverage]][project-coverage]
[![Downloads per month][badge-downloads-per-month]][project-downloads]

[![License][badge-license]][project-license]
[![Release Notes][badge-release-notes]][project-release-notes]
[![PyPI Version][badge-package-version]][project-pypi]
[![Python Versions][badge-python-versions]][project-pypi]

» [Documentation]
| [Releases]
| [Issues]
| [Source code]
| [License]
| [CrateDB]
| [Community Forum]
| [Bluesky]

## About

The CrateDB MCP Server for natural-language Text-to-SQL and documentation
retrieval specializes in CrateDB database clusters.

The Model Context Protocol ([MCP]) is a protocol that standardizes providing
context to language models and AI assistants.

### Introduction

The CrateDB Model Context Protocol (MCP) Server connects AI assistants directly
to your CrateDB clusters and the CrateDB knowledge base, enabling seamless
interaction through natural language.

It serves as a bridge between AI tools and your analytics database,
allowing you to analyze data, the cluster state, troubleshoot issues, and
perform operations using conversational prompts.

**Experimental:** Please note that the CrateDB MCP Server is an experimental
feature provided as-is without warranty or support guarantees. Enterprise
customers should use this feature at their own discretion.

### Quickstart Guide

The CrateDB MCP Server is compatible with AI assistants that support the Model
Context Protocol (MCP), either using standard input/output (`stdio`),
server-sent events (`sse`), or HTTP Streams (`http`, earlier `streamable-http`).

To use the MCP server, you need a [client that supports][MCP clients] the
protocol. The most notable ones are ChatGPT, Claude, Cline Bot, Cursor,
GitHub Copilot, Mistral AI, OpenAI Agents SDK, Windsurf, and others.

The `uvx` launcher command is provided by the [uv] package manager.
The [installation docs](#install) section includes guidelines on how to
install it on your machine.

#### Claude, Cline, Cursor, Roo Code, Windsurf
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

#### VS Code
[Add an MCP server to your VS Code user settings] to enable the MCP server
across all workspaces in your `settings.json` file.
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
[Add an MCP server to your VS Code workspace] to configure an MCP server for a
specific workspace per `.vscode/mcp.json` file. In this case, omit the
top-level `mcp` element, and start from `servers` instead.

Alternatively, VS Code can automatically detect and reuse MCP servers that
you defined in other tools, such as Claude Desktop.
See also [Automatic discovery of MCP servers].
```json
{
  "chat.mcp.discovery.enabled": true
}
```

#### Goose
Configure `extensions` in your `~/.config/goose/config.yaml`.
See also [using Goose extensions].
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

#### LibreChat
Configure `mcpServers` in your `librechat.yaml`.
See also [LibreChat and MCP] and [LibreChat MCP examples].
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

#### OCI
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

## Handbook

This section includes detailed information about how to configure and
operate the CrateDB MCP Server, and to learn about the [MCP tools] it
provides.

Tools are a powerful primitive in the Model Context Protocol (MCP) that enable
servers to expose executable functionality to clients. Through tools, LLMs can
interact with external systems, perform computations, and take actions in the
real world.

### What's inside

The CrateDB MCP Server provides two families of tools.

The **Text-to-SQL tools** talk to a CrateDB database cluster to inquire database
and table metadata, and table content.
<br>
Tool names are: `query_sql`, `get_table_columns`, `get_table_metadata`

The **documentation server tools** looks up guidelines specific to CrateDB topics,
to provide the most accurate information possible.
Relevant information is pulled from <https://cratedb.com/docs>, curated per
[cratedb-outline.yaml] through the [cratedb-about] package.
<br>
Tool names are: `get_cratedb_documentation_index`, `fetch_cratedb_docs`

Health inquiry tool: `get_cluster_health`

### Install package

The configuration snippets for AI assistants are using the `uvx` launcher
of the [uv] package manager to start the application after installing it,
like the `npx` launcher is doing it for JavaScript and TypeScript applications.
This section uses `uv tool install` to install the application persistently.

```shell
uv tool install --upgrade cratedb-mcp
```
Notes:
- We recommend using the [uv] package manager to install the `cratedb-mcp`
  package, like many other MCP servers are doing it.
  ```shell
  {apt,brew,pipx,zypper} install uv
  ```
- We recommend using `uv tool install` to install the program "user"-wide
  into your environment so you can invoke it from anywhere across your terminal
  sessions or MCP client programs / AI assistants.
- If you are unable to use `uv tool install`, you can use `uvx cratedb-mcp`
  to acquire the package and run the application ephemerally.

### Install OCI

OCI images for Docker or Podman are available on GHCR per [CrateDB MCP server OCI images].
There is a standard OCI image and an MCPO image suitable for Open WebUI.

- `ghcr.io/crate/cratedb-mcp`

  See also [Docker Hub MCP Server] and [mcp hub].

- `ghcr.io/crate/cratedb-mcpo`

  For integrating Open WebUI, the project provides an OCI MCPO image which wraps
  the MCP server using the `mcpo` proxy. See also [MCP support for Open WebUI] and
  [MCP-to-OpenAPI proxy server (mcpo)].

Probe invocation:
```shell
docker run --rm -it --entrypoint="" ghcr.io/crate/cratedb-mcp cratedb-mcp --version
```

### Configure database connectivity

Configure the `CRATEDB_CLUSTER_URL` environment variable to match your CrateDB instance.
For example, when connecting to CrateDB Cloud, use a value like
`https://admin:dZ...6LqB@testdrive.eks1.eu-west-1.aws.cratedb.net:4200/`.
When connecting to CrateDB on localhost, use `http://localhost:4200/`.
```shell
export CRATEDB_CLUSTER_URL="https://<username>:<password>@<example>.aks1.westeurope.azure.cratedb.net:4200"
```
```shell
export CRATEDB_CLUSTER_URL="http://crate:crate@localhost:4200/"
```

The `CRATEDB_MCP_HTTP_TIMEOUT` environment variable (default: 30.0) defines
the timeout for HTTP requests to CrateDB and its documentation resources
in seconds.

The `CRATEDB_MCP_DOCS_CACHE_TTL` environment variable (default: 3600) defines
the cache lifetime for documentation resources in seconds.

### Configure transport

MCP servers can be started using different transport modes. The default transport
is `stdio`, you can select another one of `{"stdio", "http", "sse", "streamable-http"}`
and supply it to the invocation like this:
```shell
cratedb-mcp serve --transport=stdio
```
NB: The `http` transport was called `streamable-http` in earlier spec iterations.

When using any of the HTTP-based options for serving the MCP interface, you can
use the CLI options `--host`, `--port` and `--path` to specify the listening address.
The default values are `localhost:8000`, where the SSE server responds to `/sse/`
and `/messages/` and the HTTP server responds to `/mcp/` by default.

Alternatively, you can use environment variables instead of CLI options.
```shell
export CRATEDB_MCP_TRANSPORT=http
export CRATEDB_MCP_HOST=0.0.0.0
export CRATEDB_MCP_PORT=8000
```
```shell
export CRATEDB_MCP_PATH=/path/in/url
```

### Security considerations

If you want to prevent agents from modifying data, i.e., permit `SELECT` statements
only, it is recommended to [create a read-only database user by using "GRANT DQL"].
```sql
CREATE USER "read-only" WITH (password = 'YOUR_PASSWORD');
GRANT DQL TO "read-only";
```
Then, include relevant access credentials in the cluster URL.
```shell
export CRATEDB_CLUSTER_URL="https://read-only:YOUR_PASSWORD@example.aks1.westeurope.azure.cratedb.net:4200"
```
The MCP Server also prohibits non-SELECT statements on the application level.
All other operations will raise a `PermissionError` exception, unless the
`CRATEDB_MCP_PERMIT_ALL_STATEMENTS` environment variable is set to a
truthy value.

### System prompt customizations

The CrateDB MCP server allows users to adjust the system prompt by either
redefining the baseline instructions or extending them with custom conventions.
Additional conventions can capture domain-specific details—such as information
required for particular ER data models —- or any other guidelines you develop
over time.

If you want to **add** custom conventions to the system prompt,
use the `--conventions` option.
```shell
cratedb-mcp serve --conventions="conventions-custom.md"
```

If you want to **replace** the standard built-in instructions prompt completely,
use the `--instructions` option.
```shell
cratedb-mcp serve --instructions="instructions-custom.md"
```

Alternatively, use the `CRATEDB_MCP_INSTRUCTIONS` and `CRATEDB_MCP_CONVENTIONS`
environment variables instead of the CLI options.

To retrieve the standard system prompt, use the `show-prompt` subcommand. By
redirecting the output to a file, you can subsequently edit its contents and
reuse it with the MCP server using the command outlined above.
```shell
cratedb-mcp show-prompt > instructions-custom.md
```

Instruction and convention fragments can be loaded from the following sources:

- HTTP(S) URLs
- Local file paths
- Standard input (when fragment is "-")
- Direct string content

Because LLMs understand Markdown well, you should also use it for writing
personal instructions or conventions.

### Operate standalone

Start MCP server with `stdio` transport (default).
```shell
cratedb-mcp serve --transport=stdio
```
Start MCP server with `sse` transport.
```shell
cratedb-mcp serve --transport=sse
```
Start MCP server with `http` transport (ex. `streamable-http`).
```shell
cratedb-mcp serve --transport=http
```
Alternatively, use the `CRATEDB_MCP_TRANSPORT` environment variable instead of
the `--transport` option.

### Operate OCI Standard

Run CrateDB database.
```shell
docker network create demo
```
```shell
docker run --rm --name=cratedb --network=demo \
  -p 4200:4200 -p 5432:5432 \
  -e CRATE_HEAP_SIZE=2g \
  crate:latest -Cdiscovery.type=single-node
```

Configure and run CrateDB MCP server.
```shell
export CRATEDB_MCP_TRANSPORT=streamable-http
export CRATEDB_MCP_HOST=0.0.0.0
export CRATEDB_MCP_PORT=8000
export CRATEDB_CLUSTER_URL=http://crate:crate@cratedb:4200/
```
```shell
docker run --rm --name=cratedb-mcp --network=demo \
  -p 8000:8000 \
  -e CRATEDB_MCP_TRANSPORT -e CRATEDB_MCP_HOST -e CRATEDB_MCP_PORT -e CRATEDB_CLUSTER_URL \
  ghcr.io/crate/cratedb-mcp
```

### Operate OCI MCPO
Invoke the CrateDB MCPO server for Open WebUI.
```shell
docker run --rm --name=cratedb-mcpo --network=demo \
  -p 8000:8000 \
  -e CRATEDB_CLUSTER_URL ghcr.io/crate/cratedb-mcpo
```

### Operate OCI on GHA
If you need instances of CrateDB and CrateDB MCP on a CI environment on GitHub Actions,
using this section might be handy, as it includes all relevant configuration options
in one go.
```yaml
services:
  cratedb:
    image: crate/crate:latest
    ports:
      - 4200:4200
      - 5432:5432
    env:
      CRATE_HEAP_SIZE: 2g
  cratedb-mcp:
    image: ghcr.io/crate/cratedb-mcp:latest
    ports:
      - 8000:8000
    env:
      CRATEDB_MCP_TRANSPORT: streamable-http
      CRATEDB_MCP_HOST: 0.0.0.0
      CRATEDB_MCP_PORT: 8000
      CRATEDB_CLUSTER_URL: http://crate:crate@cratedb:4200/
```

### Use

To connect to the MCP server using any of the available [MCP clients], use one
of the AI assistant applications, or refer to the programs in the [examples folder].

We collected a few example questions that have been tested and validated by
the team, so you may also want to try them to get started. Please remember
that LLMs can still hallucinate and give incorrect answers.

- Optimize this query: "SELECT * FROM movies WHERE release_date > '2012-12-1' AND revenue"
- Tell me about the health of the cluster
- What is the storage consumption of my tables, give it in a graph.
- How can I format a timestamp column to '2019 Jan 21'?

Please also explore the [example questions] from another shared collection.


## Project information

### Acknowledgements
Kudos to the authors of all the many software components and technologies
this project is building upon.

### Contributing
The `cratedb-mcp` package is an open-source project, and is [managed on
GitHub]. Contributions of any kind are welcome and appreciated.
To learn how to set up a development sandbox, please refer to the
[development documentation].

### Status
The software is in the alpha stage, so breaking changes may happen.
Version pinning is strongly recommended, especially if you use it as a library.


[Add an MCP server to your VS Code user settings]: https://code.visualstudio.com/docs/copilot/chat/mcp-servers#_add-an-mcp-server-to-your-user-settings
[Add an MCP server to your VS Code workspace]: https://code.visualstudio.com/docs/copilot/chat/mcp-servers#_add-an-mcp-server-to-your-workspace
[Automatic discovery of MCP servers]: https://code.visualstudio.com/docs/copilot/chat/mcp-servers#_automatic-discovery-of-mcp-servers
[CrateDB]: https://cratedb.com/database
[CrateDB MCP server OCI images]: https://github.com/orgs/crate/packages?repo_name=cratedb-mcp
[cratedb-about]: https://pypi.org/project/cratedb-about/
[cratedb-outline.yaml]: https://github.com/crate/about/blob/v0.0.4/src/cratedb_about/outline/cratedb-outline.yaml
[create a read-only database user by using "GRANT DQL"]: https://community.cratedb.com/t/create-read-only-database-user-by-using-grant-dql/2031
[development documentation]: https://github.com/crate/cratedb-mcp/blob/main/DEVELOP.md
[Docker Hub MCP Server]: https://www.docker.com/blog/introducing-docker-hub-mcp-server/
[example questions]: https://github.com/crate/about/blob/v0.0.4/src/cratedb_about/query/model.py#L17-L44
[examples folder]: https://github.com/crate/cratedb-mcp/tree/main/examples
[LibreChat and MCP]: https://www.librechat.ai/docs/features/agents#model-context-protocol-mcp
[LibreChat MCP examples]: https://www.librechat.ai/docs/configuration/librechat_yaml/object_structure/mcp_servers
[MCP]: https://modelcontextprotocol.io/introduction
[MCP clients]: https://modelcontextprotocol.io/clients
[mcp hub]: https://hub.docker.com/mcp
[MCP support for Open WebUI]: https://docs.openwebui.com/openapi-servers/mcp/
[MCP-to-OpenAPI proxy server (mcpo)]: https://github.com/open-webui/mcpo
[MCP tools]: https://modelcontextprotocol.io/docs/concepts/tools
[using Goose extensions]: https://block.github.io/goose/docs/getting-started/using-extensions/
[uv]: https://docs.astral.sh/uv/

[Bluesky]: https://bsky.app/search?q=cratedb
[Community Forum]: https://community.cratedb.com/
[Documentation]: https://github.com/crate/cratedb-mcp
[Issues]: https://github.com/crate/cratedb-mcp/issues
[License]: https://github.com/crate/cratedb-mcp/blob/main/LICENSE
[managed on GitHub]: https://github.com/crate/cratedb-mcp
[Source code]: https://github.com/crate/cratedb-mcp
[Releases]: https://github.com/surister/cratedb-mcp/releases

[badge-ci]: https://github.com/crate/cratedb-mcp/actions/workflows/tests.yml/badge.svg
[badge-bluesky]: https://img.shields.io/badge/Bluesky-0285FF?logo=bluesky&logoColor=fff&label=Follow%20%40CrateDB
[badge-coverage]: https://codecov.io/gh/crate/cratedb-mcp/branch/main/graph/badge.svg
[badge-downloads-per-month]: https://pepy.tech/badge/cratedb-mcp/month
[badge-license]: https://img.shields.io/github/license/crate/cratedb-mcp
[badge-package-version]: https://img.shields.io/pypi/v/cratedb-mcp.svg
[badge-python-versions]: https://img.shields.io/pypi/pyversions/cratedb-mcp.svg
[badge-release-notes]: https://img.shields.io/github/release/crate/cratedb-mcp?label=Release+Notes
[badge-status]: https://img.shields.io/pypi/status/cratedb-mcp.svg
[project-ci]: https://github.com/crate/cratedb-mcp/actions/workflows/tests.yml
[project-coverage]: https://app.codecov.io/gh/crate/cratedb-mcp
[project-downloads]: https://pepy.tech/project/cratedb-mcp/
[project-license]: https://github.com/crate/cratedb-mcp/blob/main/LICENSE
[project-pypi]: https://pypi.org/project/cratedb-mcp
[project-release-notes]: https://github.com/crate/cratedb-mcp/releases
