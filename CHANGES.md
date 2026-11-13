# CrateDB MCP changelog

## Unreleased
- MCP: `fetch_cratedb_docs` reads every link listed in the documentation index,
  including pages outside the permitted hosts
- MCP: Added `explain_query`, which shows how CrateDB plans or runs a SELECT query,
  with switches for `analyze`, `verbose` and `costs`
- MCP: Added `list_schemas`, `list_tables` and `describe_table`, which find tables
  step by step and return typed results. Removed `get_table_columns` and
  `get_table_metadata`, which returned every table at once
- MCP: Added a title and annotations to every tool, marking them read-only. `query_sql`
  loses its read-only mark when `CRATEDB_MCP_PERMIT_ALL_STATEMENTS` is set
- Dependencies: Updated to FastMCP 4.1, which speaks MCP protocol 2026-07-28 and
  serves its stateless HTTP requests
- OCI: Removed the `cratedb-mcpo` image. Open WebUI 0.6.31 and later connect to
  MCP servers directly, so use the standard image `ghcr.io/crate/cratedb-mcp`
  with `--transport=streamable-http`.

## v0.1.3 - 2026-11-12
- MCP: Permitted `fetch_cratedb_docs` to read from docs.cratedb.com, the new home of
  the CrateDB documentation
- MCP: `fetch_cratedb_docs` follows redirects to permitted hosts, and raises an error
  when a page answers with an error status
- Dependencies: Used the HTTP cache client of `cratedb-about`, which works with
  Hishel 1.x and keeps its cache in the user's cache directory

## v0.1.2 - 2026-05-13
- Security: Updated to `fastmcp>=3.2`, earlier versions had vulnerabilities
- Security: OCI: Apply available Debian security patches at build time

## v0.1.1 - 2026-03-22
- OCI: Updated to Python 3.14 and Debian 13 "trixie"
- Dependencies: Stopped version-pinning `pueblo` package

## v0.1.0 - 2026-03-03
- Dependencies: Updated to FastMCP 3.1

## v0.0.9 - 2025-11-03
- Security: Tamed logging of HTTPX to not reveal credentials. Thanks, @WalBeh.
- Security: Updated to `fastmcp>=2.13`, earlier versions had vulnerabilities
- Dependencies: Validated support for Python 3.14. Thanks, @surister.
- Documentation: Published to RTD at https://cratedb-mcp.readthedocs.io/

## v0.0.8 - 2025-10-14
- Rebuild for Debian CVEs

## v0.0.7 - 2025-07-28
- Instructions: Updated to [cratedb-about v0.0.8]

[cratedb-about v0.0.8]: https://github.com/crate/about/releases/tag/v0.0.8

## v0.0.6 - 2025-07-27
- OCI: Added `curl` to image
- MCP: Started using MCP tool descriptions from Python docstrings
- Instructions: Copy-editing. Wording.
- MCP: Added tool `get_table_columns`

## v0.0.5 - 2025-07-22
- MCP: Fixed defunct `get_cratedb_documentation_index` tool
- CLI: Added CLI options for user-defined prompts: `--instructions` and `--conventions`,
  both accepting file paths or URLs.
- CLI: Added subcommand `cratedb-mcp show-prompt` to display the system prompt.

## v0.0.4 - 2025-07-21
- Parameters: Added CLI option `--host` and environment variable `CRATEDB_MCP_HOST`
- Parameters: Added CLI option `--path` and environment variable `CRATEDB_MCP_PATH`
- Dependencies: Allowed updating to [FastMCP 2.10], which includes a specification
  update to [MCP spec 2025-06-18].
- OCI: Added building OCI standard image `cratedb-mcp`
- OCI: Added building OCI image `cratedb-mcpo` for Open WebUI
- Prompt: Added instructions (system prompt) to MCP server.
  Thanks, @hammerhead and @WalBeh.

[FastMCP 2.10]: https://github.com/jlowin/fastmcp/releases/tag/v2.10.0
[MCP spec 2025-06-18]: https://modelcontextprotocol.io/specification/2025-06-18/changelog

## v0.0.3 - 2025-06-18
- Dependencies: Downgraded to `fastmcp<2.7` to fix a breaking change

## v0.0.2 - 2025-05-21
- Bugfix: Removed trailing `/` on HTTP URL if it exists. Thanks, @surister.

## v0.0.1 - 2025-05-20
- Options: Renamed `CRATEDB_MCP_HTTP_URL` to `CRATEDB_CLUSTER_URL`,
  standardizing on common naming conventions
- CLI: Added subcommand `cratedb-mcp serve` using Click, with
  dedicated options `--transport` and `--port`
- Dependencies: Updated to FastMCP 2.0. It significantly expands on 1.0 by
  introducing powerful client capabilities, server proxying & composition,
  OpenAPI/FastAPI integration, and more advanced features.
  See [FastMCP 2.0 and the Official MCP SDK].
- README: Added recommendations to use a read-only database user
  to prevent agents from modifying the database content

[FastMCP 2.0 and the Official MCP SDK]: https://gofastmcp.com/getting-started/welcome#fastmcp-2-0-and-the-official-mcp-sdk

## v0.0.0 - 2025-05-16
- Project: Established project layout
- Features: First working version
- Packaging: Adjusted package dependencies for interoperability
- Packaging: Added basic CLI entry point and server launcher `cratedb-mcp`
- Documentation: Show a simple Claude Desktop configuration
- MCP docs: Add reference to medium-sized llms.txt context file
- Boilerplate: Added software tests and CI configuration
- Documentation: Added development sandbox section
- MCP docs: Used Hishel for transparently caching documentation resources,
  by default for one hour. Use the `CRATEDB_MCP_DOCS_CACHE_TTL` environment
  variable to adjust (default: 3600)
- SQL: Stronger read-only mode, using `sqlparse`
- CLI: Added option `--version` to report the installed package version
- Naming things: Started using `CRATEDB_MCP_HTTP_TIMEOUT` environment variable
