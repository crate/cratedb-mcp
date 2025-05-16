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

The CrateDB MCP Server is suitable for Text-to-SQL and documentation retrieval,
specializing on the CrateDB database.

The Model Context Protocol ([MCP]) is a protocol that standardizes providing
context to LLMs like Claude, ChatGPT, and MistralAI.

## Features

The CrateDB MCP Server lets these LLMs operate directly on CrateDB, enabling
use cases like:

- Answer questions about your data and database state.
- Help you debug and optimize queries directly on the database, for tasks
  like optimizing queries using CrateDB-specific capabilities and syntax.
- Have general conversations about any details of CrateDB and CrateDB Cloud.

To use an MCP server, you need a [client that supports] the protocol. The most
notable ones are Claude Desktop, ChatGPT desktop, OpenAI agents SDK, and Cursor.

### Details

The application includes two independent subsystems: The Text-to-SQL API talks
to a CrateDB database cluster, while the documentation server looks up guidelines
specific to CrateDB topics based on user input on demand, for example, from
<https://cratedb.com/docs>, to provide the most accurate possible information.
Relevant information is relayed per [cratedb-outline.yaml].

- Database / Text-to-SQL: `get_health`, `get_table_metadata`, `query_sql`
- Documentation server: `get_cratedb_documentation_index`, `fetch_cratedb_docs`

### Examples

These are examples of questions that have been tested and validated by the team.
Remember that LLMs can still hallucinate and give incorrect answers.

* Optimize this query: "SELECT * FROM movies WHERE release_date > '2012-12-1' AND revenue"
* Tell me about the health of the cluster
* What is the storage consumption of my tables, give it in a graph.
* How can I format a timestamp column to '2019 Jan 21'.

Please explore other [example questions] from a shared collection.

## Security considerations

**By default, the application will access the database in read-only mode.**

We do not recommend letting LLM-based agents insert or modify data by itself.
As such, only `SELECT` statements are permitted and forwarded to the database.
All other operations will raise a `ValueError` exception, unless the
`CRATEDB_MCP_PERMIT_ALL_STATEMENTS` environment variable is set to a
truthy value. This is **not** recommended.

## Install
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
  sessions or MCP client programs like Claude.
- If you are unable to use `uv tool install`, you can use `uvx cratedb-mcp`
  to acquire the package and run the application ephemerally.

## Configure

Configure the `CRATEDB_MCP_HTTP_URL` environment variable to match your CrateDB instance.
For example, when connecting to CrateDB Cloud, use a value like
`https://admin:dZ...6LqB@testdrive.eks1.eu-west-1.aws.cratedb.net:4200/`.
When connecting to CrateDB on localhost, use `http://localhost:4200/`.
```shell
export CRATEDB_MCP_HTTP_URL="https://example.aks1.westeurope.azure.cratedb.net:4200"
```
```shell
export CRATEDB_MCP_HTTP_URL="http://localhost:4200/"
```

The `CRATEDB_MCP_HTTP_TIMEOUT` environment variable (default: 30.0) defines
the timeout for HTTP requests to CrateDB and its documentation resources
in seconds.

The `CRATEDB_MCP_DOCS_CACHE_TTL` environment variable (default: 3600) defines
the cache lifetime for documentation resources in seconds.

## Usage
Start MCP server with `stdio` transport (default).
```shell
CRATEDB_MCP_TRANSPORT=stdio cratedb-mcp
```
Start MCP server with `sse` transport.
```shell
CRATEDB_MCP_TRANSPORT=sse cratedb-mcp
```

### Anthropic Claude
To use the MCP version within Claude Desktop, you can use the following configuration:

```json
{
  "mcpServers": {
    "my_cratedb": {
      "command": "uvx",
      "args": ["cratedb-mcp"],
      "env": {
        "CRATEDB_MCP_HTTP_URL": "http://localhost:4200/",
        "CRATEDB_MCP_TRANSPORT": "stdio"
      }
    }
  }
}
```

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
mcpt call query_sql --params '{"query":"SELECT * FROM sys.summits LIMIT 3"}' uvx cratedb-mcp
```
```shell
mcpt call get_table_metadata uvx cratedb-mcp
```
```shell
mcpt call get_health uvx cratedb-mcp
```

Exercise the documentation server API.
```shell
mcpt call get_cratedb_documentation_index uvx cratedb-mcp
```
```shell
mcpt call \
  fetch_cratedb_docs --params '{"link":"https://cratedb.com/docs/cloud/en/latest/_sources/cluster/integrations/mongo-cdc.md.txt"}' \
  uvx cratedb-mcp
```

## Development

To learn how to set up a development sandbox, see the [development documentation](./DEVELOP.md).


[client that supports]: https://modelcontextprotocol.io/clients#feature-support-matrix
[CrateDB]: https://cratedb.com/database
[cratedb-outline.yaml]: https://github.com/crate/about/blob/v0.0.4/src/cratedb_about/outline/cratedb-outline.yaml
[example questions]: https://github.com/crate/about/blob/v0.0.4/src/cratedb_about/query/model.py#L17-L44
[MCP]: https://modelcontextprotocol.io/introduction
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
