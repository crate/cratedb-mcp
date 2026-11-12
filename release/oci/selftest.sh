#!/bin/bash

# Fail on error.
set -e

# Display all commands.
# set -x

echo "Invoking CrateDB MCP Server"
cratedb-mcp --version

if command -v mcpo >/dev/null 2>&1; then
  echo "Invoking CrateDB MCPO"
  mcpo --host 127.0.0.1 --port 8000 -- cratedb-mcp serve --transport=stdio &
  curl --fail --silent --show-error --output /dev/null \
    --retry 30 --retry-delay 1 --retry-connrefused \
    http://127.0.0.1:8000/openapi.json
fi
