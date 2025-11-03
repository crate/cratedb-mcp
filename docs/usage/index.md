:::{include} ../_links.md
:::

(use)=
(usage)=

# Usage

:::{div}
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
:::

## Operate standalone

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
