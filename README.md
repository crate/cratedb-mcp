# CrateDB MCP Server

[![Bluesky][badge-bluesky]][target-bluesky]
[![Release Notes][badge-release-notes]][project-release-notes]

[![Status][badge-status]][target-project]
[![License][badge-license]][target-license]
[![CI][badge-ci]][project-ci]
[![Coverage][badge-coverage]][project-coverage]

» [Documentation]
| [Releases]
| [Issues]
| [Source code]
| [License]
| [CrateDB]
| [Community Forum]

# About
Model Context Protocol [MCP](https://modelcontextprotocol.io/introduction) is a protocol that standardizes providing
context to LLMs like Claude, ChatGPT and MistralAI.

CrateDB MCP server lets these LLMs operate directly on CrateDB enabling use cases like:

- Answer questions about your data and database state
- Help you debug and optimize queries directly on the database

To use a MCP server you need a [client that supports] the protocol, the most notable ones are:
Claude Desktop, ChatGTP desktop, OPenAI agents SDK and Cursor.

# Examples
For questions like optimizing queries and CrateDB specific syntax/capabilities, we encourage the
LLMs to fetch `https://cratedb.com/docs` to offer the most accurate possible information.

These are examples of questions that have been tested and validated by the team. Remember that
LLMs can still hallucinate and give incorrect answers.

* Optimize this query: "SELECT * FROM movies WHERE release_date > '2012-12-1' AND revenue"
* Tell me about the health of the cluster
* What is the storage consumption of my tables, give it in a graph.
* How can I format a timestamp column to '2019 Jan 21'.

# Data integrity
We do not recommend letting the LLMs insert data or modify columns by itself, as such we tell the
LLMs to only allow 'SELECT' statements in the `cratedb_sql` tool, you can jailbreak this against
our recommendation.

# Install
```shell
uv tool install --upgrade git+https://github.com/crate/cratedb-mcp
```
Note: We recommend to use `uv tool install` to install the program "user"-wide
into your environment so you can use it across your terminal or MCP client
sessions like Claude.

# Configure

Configure the `CRATEDB_MCP_HTTP_URL` environment variable to match your CrateDB instance.
For example, when connecting to CrateDB Cloud, use a value like
`https://admin:dZ...6LqB@testdrive.eks1.eu-west-1.aws.cratedb.net:4200/`.
When connecting to CrateDB on localhost, use `http://localhost:4200/`.
```shell
export CRATEDB_MCP_HTTP_URL="http://localhost:4200/"
```
```shell
export CRATEDB_MCP_HTTP_URL="https://example.aks1.westeurope.azure.cratedb.net:4200"
```

# Usage
Start MCP server with `stdio` transport (default).
```shell
CRATEDB_MCP_TRANSPORT=stdio cratedb-mcp
```
Start MCP server with `sse` transport.
```shell
CRATEDB_MCP_TRANSPORT=sse cratedb-mcp
```
Note: If you are unable to use `uv tool install`, please use
`uv run cratedb-mcp` to acquire and run the package ephemerally.

# Simple Claude configuration
To use the MCP version within Claude Desktop, you can use the following configuration:

```json
{
  "mcpServers": {
    "my_cratedb": {
      "command": "uvx",
      "args": ["--python", "3.13", "--from", "git+https://github.com/crate/cratedb-mcp", "cratedb-mcp"],
      "env": {
        "CRATEDB_MCP_HTTP_URL": "http://localhost:4200/",
        "CRATEDB_MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```


## Development

To learn how to set up a development sandbox, see the [development documentation](./DEVELOP.md).


[CrateDB]: https://cratedb.com/database
[issue tracker]: https://github.com/crate/cratedb-mcp/issues

[Community Forum]: https://community.cratedb.com/
[Documentation]: https://github.com/crate/cratedb-mcp
[Issues]: https://github.com/crate/cratedb-mcp/issues
[License]: https://github.com/crate/cratedb-mcp/blob/main/LICENSE
[managed on GitHub]: https://github.com/crate/cratedb-mcp
[Source code]: https://github.com/crate/cratedb-mcp
[Releases]: https://github.com/surister/cratedb-mcp/releases

[badge-ci]: https://github.com/crate/cratedb-mcp/actions/workflows/tests.yml/badge.svg
[badge-coverage]: https://codecov.io/gh/crate/cratedb-mcp/branch/main/graph/badge.svg
[badge-bluesky]: https://img.shields.io/badge/Bluesky-0285FF?logo=bluesky&logoColor=fff&label=Follow%20%40CrateDB
[badge-license]: https://img.shields.io/github/license/crate/cratedb-mcp
[badge-release-notes]: https://img.shields.io/github/release/crate/cratedb-mcp?label=Release+Notes
[badge-status]: https://img.shields.io/badge/status--alpha-orange
[project-ci]: https://github.com/crate/cratedb-mcp/actions/workflows/tests.yml
[project-coverage]: https://app.codecov.io/gh/crate/cratedb-mcp
[project-release-notes]: https://github.com/crate/cratedb-mcp/releases
[target-bluesky]: https://bsky.app/search?q=cratedb
[target-license]: https://github.com/crate/cratedb-mcp/blob/main/LICENSE
[target-project]: https://github.com/crate/cratedb-mcp
[client that supports]: https://modelcontextprotocol.io/clients#feature-support-matrix
