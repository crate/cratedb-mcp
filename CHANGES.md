# CrateDB MCP changelog

## Unreleased

Upgrading from 0.1.x:
- Images: the `cratedb-mcpo` image is gone. With Open WebUI 0.6.31 or later, run the
  standard image `ghcr.io/crate/cratedb-mcp` and add it as a connection of type
  MCP (Streamable HTTP).
- Tools: `fetch_cratedb_docs` keeps the pages it fetched in memory, and no longer in the
  cache file of `cratedb-about`, such as `~/.cache/cratedb-about/.hishel.sqlite`. Delete
  that file unless the `cratedb-about` command uses it.
- Logs: the log shows statement text only when the server runs with `--debug` or with
  `CRATEDB_MCP_DEBUG=true` set, as in `cratedb-mcp --debug serve`.
- Settings: the server does not start when `CRATEDB_CLUSTER_URL` is not an http or https
  URL with a host. Percent-encode `/`, `#`, `?` and `@` in a user name or password, such
  as `/` as `%2F`.
- Settings: the server does not start when `CRATEDB_MCP_HTTP_TIMEOUT` is not a number of
  seconds above zero. Remove the setting or correct it.
- Tools: `fetch_cratedb_docs` no longer fetches a GitHub page that is not a link of the
  documentation index.
- Packaging: the server needs version 2 of the MCP SDK. Where an environment holds
  `mcp<2`, install the server apart from it, for example with `uv tool install cratedb-mcp`.
- Instructions: the text sent to clients is new and much shorter, and it sets no
  persona. If a setup relied on the old text, pass your own with `--instructions` or
  `CRATEDB_MCP_INSTRUCTIONS`.
- Tools: a CrateDB error fails the call, with `isError` set and CrateDB's message and
  error code as its text. Clients that read the `error` field of a `query_sql` or
  `get_cluster_health` result check `isError` instead.
- Tools: `query_sql` returns at most 100 rows. `CRATEDB_MCP_MAX_ROWS` changes the cap, and
  `max_rows` asks for up to 1,000 rows, or the cap when it is larger. Check `truncated`
  when a complete result matters.
- Tools: `get_cratedb_documentation_index` returns an object with the pages in `pages`,
  instead of a list. `get_cluster_health` returns at most 100 rows, the most severe
  first, or as many as `CRATEDB_MCP_MAX_ROWS` sets. Check `truncated` when every row
  matters.

Changes:
- OCI: Removed the `cratedb-mcpo` image. Open WebUI 0.6.31 and later connect to
  MCP servers directly, so use the standard image `ghcr.io/crate/cratedb-mcp`
  with `--transport=streamable-http`.
- OCI: The image built from a release tag reports exactly the tag's version
- MCP: The server keeps fetched documentation pages in memory for
  `CRATEDB_MCP_DOCS_CACHE_TTL` seconds, and in no file
- CLI: `python -m cratedb_mcp` runs the `cratedb-mcp` command, with the same
  subcommands and options, instead of exiting without a word
- MCP: The log names the tool, the duration and the row count of each call to CrateDB,
  and holds the statement text only at debug level
- CLI: Added `--debug` and the `CRATEDB_MCP_DEBUG` environment variable, which log at
  debug level, with the first 50 characters of each statement the model sends
- CLI: The server reads `CRATEDB_CLUSTER_URL` when it starts, and does not start when it
  is not an http or https URL with a host
- CLI: The server does not start when `CRATEDB_MCP_HTTP_TIMEOUT` is not a number above zero
- Tests: The software tests answer requests for documentation pages and remote
  instructions from memory
- Shipping: Pushing a release tag creates the GitHub release, with the tag's section of
  this file as its notes
- MCP: `fetch_cratedb_docs` reads every link listed in the documentation index,
  including pages outside the permitted hosts
- MCP: `fetch_cratedb_docs` fetches the links of the documentation index and pages on
  cratedb.com and docs.cratedb.com. It checks the address of every redirect before it
  follows it, reads only uncompressed text, at most 1 MB of it, and ends each call within
  `CRATEDB_MCP_HTTP_TIMEOUT` once it is connected, the redirects included
- Dependencies: Updated to FastMCP 4.1, which speaks MCP protocol 2026-07-28 and
  serves its stateless HTTP requests
- CLI: The server starts without asking PyPI for a newer FastMCP release, unless
  `FASTMCP_CHECK_FOR_UPDATES` is set
- Instructions: The server sends its own short instructions text and no longer adds
  the general CrateDB text of `cratedb-about`. Pass `--instructions` to send another text.
- MCP: Added a title and annotations to every tool, marking them read-only. `query_sql`
  loses its read-only mark when `CRATEDB_MCP_PERMIT_ALL_STATEMENTS` is set
- MCP: Every tool fails a call it cannot complete with the MCP error flag `isError` and
  a message that says why it failed. CrateDB's errors are no longer returned as results
- MCP: A query that times out tells the model to narrow it instead of retrying
- MCP: `query_sql`, `get_cluster_health` and `get_cratedb_documentation_index` declare
  the fields of their results
- MCP: `query_sql` returns at most 100 rows and 50,000 characters of rows, marks a cut
  result with `truncated` and a `note`, and takes `max_rows` for up to 1,000 rows.
  `CRATEDB_MCP_MAX_ROWS` and `CRATEDB_MCP_MAX_CHARS` change the defaults
- CLI: The server does not start when `CRATEDB_MCP_MAX_ROWS` or `CRATEDB_MCP_MAX_CHARS` is
  not a whole number above zero
- MCP: `get_cluster_health` and `get_cratedb_documentation_index` cut their answers to the
  result caps, and say so in `truncated` and `note`

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
