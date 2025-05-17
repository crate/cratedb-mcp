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

The CrateDB MCP Server for natural language Text-to-SQL and documentation
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
Context Protocol (MCP), either using standard input/output (stdio),
server-sent events (SSE), or HTTP Streams (streamable-http).

To use the MCP server, you need a [client that supports] the protocol. The most
notable ones are ChatGPT, Claude, Cline, Cursor, GitHub Copilot, Mistral AI,
OpenAI Agents SDK, Windsurf, and others.

The `uvx` launcher command is provided by the [uv] package manager.
The [installation docs](#install) section includes guidelines how to
install it on your machine.

#### Claude, Cursor, Windsurf

Add the following configuration to your AI assistant's settings to enable the
CrateDB MCP Server:
```json
{
  "mcpServers": {
    "cratedb-mcp": {
      "command": "uvx",
      "args": ["cratedb-mcp", "serve"],
      "env": {
        "CRATEDB_CLUSTER_URL": "http://localhost:4200/",
        "CRATEDB_MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

#### VS Code Copilot Chat

Add the following configuration to your VS Code settings:
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

The **Text-to-SQL API** talks to a CrateDB database cluster to inquire database
and table metadata, and table content.
<br>
Tool names are: `get_health`, `get_table_metadata`, `query_sql`

The **Documentation API** looks up guidelines specific to CrateDB topics,
to provide the most accurate information possible.
Relevant information is pulled from <https://cratedb.com/docs>, curated per
[cratedb-outline.yaml] through the [cratedb-about] package.
<br>
Tool names are: `get_cratedb_documentation_index`, `fetch_cratedb_docs`

### Examples

We collected a few examples of questions that have been tested and validated by
the team, so you may also want to try them. Please remember that LLMs can still
hallucinate and give incorrect answers.

* Optimize this query: "SELECT * FROM movies WHERE release_date > '2012-12-1' AND revenue"
* Tell me about the health of the cluster
* What is the storage consumption of my tables, give it in a graph.
* How can I format a timestamp column to '2019 Jan 21'.

Please also explore the [example questions] from another shared collection.

### Security considerations

**By default, the application will access the database in read-only mode.**

We do not recommend letting LLM-based agents insert or modify data by itself.
As such, only `SELECT` statements are permitted and forwarded to the database.
All other operations will raise a `ValueError` exception, unless the
`CRATEDB_MCP_PERMIT_ALL_STATEMENTS` environment variable is set to a
truthy value. This is **not** recommended.

### Install

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
- We recommend to use `uv tool install` to install the program "user"-wide
  into your environment so you can invoke it from anywhere across your terminal
  sessions or MCP client programs / AI assistants.
- If you are unable to use `uv tool install`, you can use `uvx cratedb-mcp`
  to acquire the package and run the application ephemerally.

### Configure

Configure the `CRATEDB_CLUSTER_URL` environment variable to match your CrateDB instance.
For example, when connecting to CrateDB Cloud, use a value like
`https://admin:dZ...6LqB@testdrive.eks1.eu-west-1.aws.cratedb.net:4200/`.
When connecting to CrateDB on localhost, use `http://localhost:4200/`.
```shell
export CRATEDB_CLUSTER_URL="https://example.aks1.westeurope.azure.cratedb.net:4200"
```
```shell
export CRATEDB_CLUSTER_URL="http://localhost:4200/"
```

The `CRATEDB_MCP_HTTP_TIMEOUT` environment variable (default: 30.0) defines
the timeout for HTTP requests to CrateDB and its documentation resources
in seconds.

The `CRATEDB_MCP_DOCS_CACHE_TTL` environment variable (default: 3600) defines
the cache lifetime for documentation resources in seconds.

### Usage

Start MCP server with `stdio` transport (default).
```shell
cratedb-mcp serve --transport=stdio
```
Start MCP server with `sse` transport.
```shell
cratedb-mcp serve --transport=sse
```
Start MCP server with `streamable-http` transport.
```shell
cratedb-mcp serve --transport=streamable-http
```
Alternatively, use the `CRATEDB_MCP_TRANSPORT` environment variable instead of
the `--transport` option.

### Dry-run

You can use [mcptools], a Swiss Army Knife for MCP Servers, to talk to the
CrateDB MCP Server from the command line. The following operations do not
require a language model.

Install software packages.
```shell
brew tap f/mcptools
brew install mcp uv
```

Explore the Text-to-SQL API.
```shell
mcpt call query_sql --params '{"query":"SELECT * FROM sys.summits LIMIT 3"}' uvx cratedb-mcp serve
```
```shell
mcpt call get_table_metadata uvx cratedb-mcp serve
```
```shell
mcpt call get_health uvx cratedb-mcp serve
```

Exercise the documentation server API.
```shell
mcpt call get_cratedb_documentation_index uvx cratedb-mcp serve
```
```shell
mcpt call \
  fetch_cratedb_docs --params '{"link":"https://cratedb.com/docs/cloud/en/latest/_sources/cluster/integrations/mongo-cdc.md.txt"}' \
  uvx cratedb-mcp serve
```

### Development

To learn how to set up a development sandbox, see the [development documentation].


[client that supports]: https://modelcontextprotocol.io/clients
[CrateDB]: https://cratedb.com/database
[cratedb-about]: https://pypi.org/project/cratedb-about/
[cratedb-outline.yaml]: https://github.com/crate/about/blob/v0.0.4/src/cratedb_about/outline/cratedb-outline.yaml
[development documentation]: https://github.com/crate/cratedb-mcp/blob/main/DEVELOP.md
[example questions]: https://github.com/crate/about/blob/v0.0.4/src/cratedb_about/query/model.py#L17-L44
[MCP]: https://modelcontextprotocol.io/introduction
[MCP tools]: https://modelcontextprotocol.io/docs/concepts/tools
[mcptools]: https://github.com/f/mcptools
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
