# CrateDB MCP changelog

## Unreleased
- Parameters: Added CLI option `--host` and environment variable `CRATEDB_MCP_HOST`
- Parameters: Added CLI option `--path` and environment variable `CRATEDB_MCP_PATH`
- Dependencies: Allowed updating to [FastMCP 2.10], which includes a specification
  update to [MCP spec 2025-06-18].
- OCI: Added building OCI standard image `cratedb-mcp`
- OCI: Added building OCI image `cratedb-mcpo` for Open WebUI

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
