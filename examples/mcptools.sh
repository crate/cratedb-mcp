#!/usr/bin/env bash

set -euo pipefail

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

if ! command -v mcptools >/dev/null 2>&1; then
  echo mcptools not installed, skipping.
  echo "Skipped."
  exit 0
fi

# Some systems do not provide the `mcpt` alias.
alias mcpt=mcptools

# Display available MCP tools.
mcpt tools cratedb-mcp serve

# Explore the Text-to-SQL tools.
mcpt call query_sql --params '{"query":"SELECT * FROM sys.summits LIMIT 3"}' cratedb-mcp serve
mcpt call get_table_columns cratedb-mcp serve
mcpt call get_table_metadata cratedb-mcp serve
mcpt call get_cluster_health cratedb-mcp serve

# Exercise the documentation server tools.
mcpt call get_cratedb_documentation_index cratedb-mcp serve
mcpt call \
  fetch_cratedb_docs --params '{"link":"https://cratedb.com/docs/cloud/en/latest/_sources/cluster/integrations/mongo-cdc.md.txt"}' \
  cratedb-mcp serve

echo "Ready."
