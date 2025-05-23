# MCP research notes

## What is it?

A: It's effectively just OpenAPI for LLMs._

A: It is sometimes described as "the USB-C port for AI", providing a uniform
way to connect LLMs to resources they can use.

## Specification

The [MCP specification](https://spec.modelcontextprotocol.io).

### Introduction

- MCP: an in-depth introduction
  https://www.speakeasy.com/mcp/mcp-tutorial
  https://news.ycombinator.com/item?id=43972334

### Evolution

> The spec for the MCP transport is changing from SSE to
> [Streamable HTTP](https://spec.modelcontextprotocol.io/specification/2025-03-26/basic/transports/#streamable-http).
:::{seealso}
- https://github.com/stuzero/pg-mcp-server/issues/13
- https://github.com/modelcontextprotocol/python-sdk/issues/405
:::

## Gallery

- <https://github.com/punkpeye/awesome-mcp-servers>

## Articles

- What we learned when converting complex OpenAPI specs to MCP servers
  https://www.stainless.com/blog/what-we-learned-converting-complex-openapi-specs-to-mcp-servers

## Package registries

- <https://mcp.so/>
- <https://mcphub.tools/>
- <https://smithery.ai/>
- <https://glama.ai/mcp/servers>
- <https://www.mcpserverfinder.com/>
- <https://www.pulsemcp.com/>
- All: [MCP Registry Registry MCP Server](https://github.com/mastra-ai/mastra/blob/4af513ca1a8e94354c788e40e900d49fbf1c9f86/packages/mcp-registry-registry/src/registry/registry.ts)
- https://github.com/chatmcp/mcpso
- https://mcpservers.org/

## Clients

- [Using an MCP client](https://github.com/modelcontextprotocol/servers/tree/main#using-an-mcp-client)
- [Example Clients](https://modelcontextprotocol.io/clients)
- https://github.com/crate/crate-clients-tools/issues/247

## Servers

- [MCP example servers](https://modelcontextprotocol.io/examples)

### Frameworks

- https://github.com/modelcontextprotocol/python-sdk
- https://github.com/tadata-org/fastapi_mcp
- https://github.com/logiscape/mcp-sdk-php

### Databases

- [PostgreSQL](https://github.com/modelcontextprotocol/servers/blob/main/src/postgres) - Read-only database access with schema inspection, see [@modelcontextprotocol/server-postgres](https://www.npmjs.com/package/@modelcontextprotocol/server-postgres).
- [DBHub](https://github.com/bytebase/dbhub/) - Universal database MCP server connecting to MySQL, PostgreSQL, SQLite, DuckDB and etc.
- [JDBC](https://github.com/quarkiverse/quarkus-mcp-servers/tree/main/jdbc) - Connect to any JDBC-compatible database and query, insert, update, delete, and more. Supports MySQL, PostgreSQL, Oracle, SQL Server, sqllite and [more](https://github.com/quarkiverse/quarkus-mcp-servers/tree/main/jdbc#supported-jdbc-variants).
- https://github.com/stuzero/pg-mcp ([discuss](https://news.ycombinator.com/item?id=43520953))
- https://github.com/runekaagaard/mcp-alchemy
- https://github.com/OpenLinkSoftware/mcp-sqlalchemy-server
- https://github.com/googleapis/genai-toolbox

### Copilots
- https://github.blog/changelog/2025-05-13-agent-mode-mcp-and-next-edit-suggestions-come-to-github-copilot-in-visual-studio-17-14/#mcp-support
- https://github.com/VikashLoomba/copilot-mcp

### Docs and Knowledge

- https://mcp.so/server/mcp-documentation-server/mahawi1992
- https://mcp.so/server/mcp-documentation-server/DotNaos
- Mastra MCP Documentation Server
  - https://mastra.ai/blog/introducing-mastra-mcp
  - https://github.com/mastra-ai/mastra/tree/main/packages/mcp-docs-server
- https://github.com/sammcj/mcp-package-docs
- https://github.com/SubaashNair/documentation-mcp-server
- https://mintlify.com/blog/generate-mcp-servers-for-your-docs
- https://mintlify.com/blog/simplifying-docs-with-llms-txt
- https://llmstxt.org/
- https://github.com/mrjoshuak/godoc-mcp
- https://github.com/jonathanfischer97/juliadoc-mcp
- https://github.com/dazeb/markdown-downloader

### Others

- https://github.com/jjsantos01/qgis_mcp
- https://github.com/ahujasid/blender-mcp
- https://github.com/Simon-Kansara/ableton-live-mcp-server
- https://github.com/ihrpr/mcp-server-jupyter
- https://github.com/fusedio/fused-mcp
- https://pypi.org/project/mcp-atlassian/
- https://pypi.org/project/mcp-server-fetch/
- https://mcp.so/server/mcp-installer
- [pypi-search](https://github.com/nomicode/cline/tree/main/MCP/pypi-search)
- https://github.com/nerding-io/n8n-nodes-mcp
- https://github.com/opensumi/core
- https://github.com/awslabs/mcp
- https://github.com/Upsonic/Upsonic
- https://github.com/anaisbetts/mcp-installer
- https://github.com/mark3labs/mcp-go
- https://github.com/modelcontextprotocol/inspector
- https://github.com/lastmile-ai/mcp-agent
  > [mcp-agent](https://github.com/lastmile-ai/mcp-agent) is a simple, composable framework to build
  > agents using [Model Context Protocol](https://modelcontextprotocol.io/introduction).
  > This one also looks interesting, including [something about marimo](https://github.com/lastmile-ai/mcp-agent#marimo).
- https://github.com/drillan/sphinx-mcp-test
- https://github.com/github/github-mcp-server
- https://github.com/varunneal/spotify-mcp
- https://github.com/BrowserMCP/mcp
- https://github.com/TuanKiri/weather-mcp-server
- https://github.com/mkummer225/google-sheets-mcp
- https://github.com/LaurieWired/GhidraMCP ([discuss](https://news.ycombinator.com/item?id=43474490))
- https://github.com/microsoft/playwright-mcp ([discuss](https://news.ycombinator.com/item?id=43485740))
- https://openai.github.io/openai-agents-python/mcp/ ([discuss](https://news.ycombinator.com/item?id=43485566))
- https://github.com/janwilmake/openapi-mcp-server
- https://gitmcp.io/
- https://github.com/heltonteixeira/ragdocs
- https://github.com/microsoft/semanticworkbench/tree/main/mcp-servers
- https://github.com/JetBrains/mcp-jetbrains

## Composition
- https://github.com/themanojdesai/python-a2a
- https://github.com/Klavis-AI/klavis
- https://github.com/activepieces/activepieces
- https://github.com/mannaandpoem/OpenManus
- https://github.com/OpenManus/OpenManus-RL
- https://github.com/All-Hands-AI/OpenHands
