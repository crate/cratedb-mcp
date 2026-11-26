:::{include} _links.md
:::

(index)=

# CrateDB MCP Server

:::{include} readme.md
:start-line: 1
:end-line: 74
:::

## Quickstart Guide

:::{div}
The CrateDB MCP Server is compatible with AI assistants that support the Model
Context Protocol (MCP), either using standard input/output (`stdio`)
or HTTP Streams (`http`, earlier `streamable-http`).

To use the MCP server, you need a [client that supports][MCP clients] the
protocol. The most notable ones are ChatGPT, Claude, Cline Bot, Cursor,
GitHub Copilot, Mistral AI, OpenAI Agents SDK, Windsurf, and others.
:::

This section includes detailed information about how to configure and
operate the CrateDB MCP Server.

::::{grid} 2 2 2 3
:gutter: 2

:::{grid-item-card} {material-regular}`download;2em` &nbsp; Install
:link: install
:link-type: ref
:::

:::{grid-item-card} {material-regular}`display_settings;2em` &nbsp; Configure
:link: configure
:link-type: ref
:::

:::{grid-item-card} {material-regular}`menu_book;2em` &nbsp; Use
:link: usage
:link-type: ref
:::

::::

## What's inside

:::{div}
This section includes information about the included [MCP tools].

Tools are a powerful primitive in the Model Context Protocol (MCP) that enable
servers to expose executable functionality to clients. Through tools, LLMs can
interact with external systems, perform computations, and take actions in the
real world.
:::

The CrateDB MCP Server provides three families of tools.

:::{div}

:Text-to-SQL:

  The tools `list_schemas`, `list_tables`, `describe_table`,
  `analyze_table_layout`, `query_sql` and `explain_query` talk to a CrateDB
  database cluster to inquire database and table metadata, shard layout,
  table content, and query plans.

:Documentation inquiry:

  The tools `get_cratedb_documentation_index` and `fetch_cratedb_docs`
  look up guidelines specific to CrateDB topics,
  to provide the most accurate information possible.
  They use the documentation index of the [cratedb-about] package, curated per
  [cratedb-outline.yaml]. `fetch_cratedb_docs` fetches the links of that index and
  other pages on `cratedb.com` and `docs.cratedb.com`, as text of at most 1 MB.

:Health status:

  The tool `get_cluster_health` returns the health of each table and
  partition from `sys.health`, most severe first, and `diagnose_workload` lists
  slow, failed and running data statements and the latencies per statement type.
:::

A tool is marked as deprecated for one minor release before it is removed.

:::{note}
**Experimental:** Please note that the CrateDB MCP Server is an experimental
feature provided as-is without warranty or support guarantees. Enterprise
customers should use this feature at their own discretion.
:::

### Values

A tool returns each value as CrateDB sends it, with three exceptions. A TIMESTAMP value
comes back as ISO 8601 text, with milliseconds when they are not zero, such as
`2025-02-06T05:15:36.123Z`. A TIMESTAMP WITHOUT TIME ZONE value has no `Z`. A DATE value
comes back as the date alone, such as `2025-07-01`, and a year outside 1 to 9999 comes as a
sign and at least five digits, such as `+10000-01-01`. A NUMERIC value comes back as text
with every digit CrateDB sends, because most clients read a JSON number as a float,
which keeps about 16 digits. Values inside an OBJECT column stay as CrateDB sends them,
because CrateDB reports no types for them.

### Errors and limits

When a tool cannot do what it was asked, the call fails: its result carries the
MCP error flag `isError` and a message that says why it failed, such as CrateDB's
error message with its error code. When a tool cuts its answer to a limit, the
call succeeds and says so in `truncated` and `note`.


:::{toctree}
:caption: Handbook
:maxdepth: 1
:hidden:

install/index
configure/index
usage/index
:::

:::{toctree}
:caption: Workbench
:maxdepth: 1
:hidden:

Changelog <changes>
Sandbox <sandbox>
Backlog <backlog>
Research <research>
:::
