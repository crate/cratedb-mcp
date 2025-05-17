#!/usr/bin/env sh

# CrateDB MCP Server example with `mcptools`
#
# You can use the `mcptools` package, a Swiss Army Knife for MCP Servers,
# to talk to the CrateDB MCP Server from the command line. The following
# operations do not require a language model.
#
# -- https://github.com/f/mcptools
#
# Install software packages.
# brew tap f/mcptools
# brew install mcp uv

# Explore the Text-to-SQL tools.
mcpt call query_sql --params '{"query":"SELECT * FROM sys.summits LIMIT 3"}' uvx cratedb-mcp serve
mcpt call get_table_metadata uvx cratedb-mcp serve
mcpt call get_health uvx cratedb-mcp serve

# Exercise the documentation server tools.
mcpt call get_cratedb_documentation_index uvx cratedb-mcp serve
mcpt call \
  fetch_cratedb_docs --params '{"link":"https://cratedb.com/docs/cloud/en/latest/_sources/cluster/integrations/mongo-cdc.md.txt"}' \
  uvx cratedb-mcp serve
