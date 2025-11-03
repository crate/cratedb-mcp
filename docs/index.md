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
Context Protocol (MCP), either using standard input/output (`stdio`),
server-sent events (`sse`), or HTTP Streams (`http`, earlier `streamable-http`).

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

The CrateDB MCP Server provides two families of tools.

:::{div}

:Text-to-SQL:

  The tools `query_sql`, `get_table_columns`, and `get_table_metadata`
  talk to a CrateDB database cluster to inquire database
  and table metadata, and table content.

:Documentation inquiry:

  The tools `get_cratedb_documentation_index` and `fetch_cratedb_docs`
  look up guidelines specific to CrateDB topics,
  to provide the most accurate information possible.
  Relevant information is pulled from <https://cratedb.com/docs>, curated per
  [cratedb-outline.yaml] through the [cratedb-about] package.

:Health status:

  The tool `get_cluster_health` returns cluster health information derived
  from CrateDB's system tables.
:::

:::{note}
**Experimental:** Please note that the CrateDB MCP Server is an experimental
feature provided as-is without warranty or support guarantees. Enterprise
customers should use this feature at their own discretion.
:::


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
