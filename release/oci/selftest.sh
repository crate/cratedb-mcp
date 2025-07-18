#!/bin/bash

# Fail on error.
set -e

# Display all commands.
# set -x

echo "Invoking CrateDB MCP Server"
cratedb-mcp --version
