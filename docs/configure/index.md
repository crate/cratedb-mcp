(configure)=

# Configuration

## Configure database connectivity

Configure the `CRATEDB_CLUSTER_URL` environment variable to match your CrateDB instance.
For example, when connecting to CrateDB Cloud, use a value like
`https://admin:dZ...6LqB@testdrive.eks1.eu-west-1.aws.cratedb.net:4200/`.
When connecting to CrateDB on localhost, use `http://localhost:4200/`.
```shell
export CRATEDB_CLUSTER_URL="https://<username>:<password>@<example>.aks1.westeurope.azure.cratedb.net:4200"
```
```shell
export CRATEDB_CLUSTER_URL="http://crate:crate@localhost:4200/"
```

The `CRATEDB_MCP_HTTP_TIMEOUT` environment variable (default: 30.0) defines
the timeout for HTTP requests to CrateDB and its documentation resources
in seconds.

The `CRATEDB_MCP_DOCS_CACHE_TTL` environment variable (default: 3600) defines
the cache lifetime for documentation resources in seconds.

## Configure transport

MCP servers can be started using different transport modes. The default transport
is `stdio`, you can select another one of `{"stdio", "http", "sse", "streamable-http"}`
and supply it to the invocation like this:
```shell
cratedb-mcp serve --transport=stdio
```
NB: The `http` transport was called `streamable-http` in earlier spec iterations.

When using any of the HTTP-based options for serving the MCP interface, you can
use the CLI options `--host`, `--port` and `--path` to specify the listening address.
The default values are `localhost:8000`, where the SSE server responds to `/sse/`
and `/messages/` and the HTTP server responds to `/mcp/` by default.

Alternatively, you can use environment variables instead of CLI options.
```shell
export CRATEDB_MCP_TRANSPORT=http
export CRATEDB_MCP_HOST=0.0.0.0
export CRATEDB_MCP_PORT=8000
```
```shell
export CRATEDB_MCP_PATH=/path/in/url
```

## Security considerations

If you want to prevent agents from modifying data, i.e., permit `SELECT` statements
only, it is recommended to [create a read-only database user by using "GRANT DQL"].
```sql
CREATE USER "read-only" WITH (password = 'YOUR_PASSWORD');
GRANT DQL TO "read-only";
```
Then, include relevant access credentials in the cluster URL.
```shell
export CRATEDB_CLUSTER_URL="https://read-only:YOUR_PASSWORD@example.aks1.westeurope.azure.cratedb.net:4200"
```
The MCP Server also prohibits non-SELECT statements on the application level.
All other operations will raise a `PermissionError` exception, unless the
`CRATEDB_MCP_PERMIT_ALL_STATEMENTS` environment variable is set to a
truthy value.

## System prompt customizations

The CrateDB MCP server allows users to adjust the system prompt by either
redefining the baseline instructions or extending them with custom conventions.
Additional conventions can capture domain-specific details—such as information
required for particular ER data models —- or any other guidelines you develop
over time.

If you want to **add** custom conventions to the system prompt,
use the `--conventions` option.
```shell
cratedb-mcp serve --conventions="conventions-custom.md"
```

If you want to **replace** the standard built-in instructions prompt completely,
use the `--instructions` option.
```shell
cratedb-mcp serve --instructions="instructions-custom.md"
```

Alternatively, use the `CRATEDB_MCP_INSTRUCTIONS` and `CRATEDB_MCP_CONVENTIONS`
environment variables instead of the CLI options.

To retrieve the standard system prompt, use the `show-prompt` subcommand. By
redirecting the output to a file, you can subsequently edit its contents and
reuse it with the MCP server using the command outlined above.
```shell
cratedb-mcp show-prompt > instructions-custom.md
```

Instruction and convention fragments can be loaded from the following sources:

- HTTP(S) URLs
- Local file paths
- Standard input (when fragment is "-")
- Direct string content

Because LLMs understand Markdown well, you should also use it for writing
personal instructions or conventions.
