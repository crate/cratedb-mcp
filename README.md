# CrateDB MCP Server

[![Bluesky][badge-bluesky]][target-bluesky]
[![Status][badge-status]][target-project]
[![License][badge-license]][target-license]

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

[CrateDB]: https://cratedb.com/database
[issue tracker]: https://github.com/crate/cratedb-mcp/issues

[Community Forum]: https://community.cratedb.com/
[Documentation]: https://github.com/crate/cratedb-mcp
[Issues]: https://github.com/crate/cratedb-mcp/issues
[License]: https://github.com/crate/cratedb-mcp/blob/main/LICENSE
[managed on GitHub]: https://github.com/crate/cratedb-mcp
[Source code]: https://github.com/crate/cratedb-mcp
[Releases]: https://github.com/surister/cratedb-mcp/releases

[badge-bluesky]: https://img.shields.io/badge/Bluesky-0285FF?logo=bluesky&logoColor=fff&label=Follow%20%40CrateDB
[badge-issues]: https://img.shields.io/github/issues/crate/cratedb-mcp
[badge-license]: https://img.shields.io/github/license/crate/cratedb-mcp
[badge-release-notes]: https://img.shields.io/badge/Release%20Notes-v0.0.0-blue
[badge-status]: https://img.shields.io/badge/status--alpha-orange
[target-bluesky]: https://bsky.app/search?q=cratedb
[target-license]: https://github.com/crate/cratedb-mcp/blob/main/LICENSE
[target-project]: https://github.com/crate/cratedb-mcp
[client that supports]: https://modelcontextprotocol.io/clients#feature-support-matrix