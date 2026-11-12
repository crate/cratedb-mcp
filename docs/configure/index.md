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
is `stdio`, you can select `http` instead. Over HTTP, the server requires a
bearer token, see [Configure HTTP access](#configure-http-access).
```shell
export CRATEDB_MCP_AUTH_TOKEN="$(openssl rand -hex 32)"
cratedb-mcp serve --transport=http
```
NB: The `http` transport was called `streamable-http` in earlier spec iterations.
The `sse` transport is deprecated, because the MCP specification removed it.

When serving over HTTP, you can use the CLI options `--host`, `--port` and
`--path` to specify the listening address. The default values are
`127.0.0.1:8000`, and the server responds to `/mcp` by default.

Alternatively, you can use environment variables instead of CLI options.
```shell
export CRATEDB_MCP_TRANSPORT=http
export CRATEDB_MCP_HOST=127.0.0.1
export CRATEDB_MCP_PORT=8000
```
```shell
export CRATEDB_MCP_PATH=/path/in/url
```

## Configure result size

Every row `query_sql` returns lands in the model's context, so results are cut.
By default a result holds at most 100 rows and 50,000 characters of rows. The
model can ask for up to 1,000 rows with the `max_rows` argument. The character
cap also bounds the plans `explain_query` returns. When rows are cut, the result
says so in `truncated` and explains it in `note`.
```shell
export CRATEDB_MCP_MAX_ROWS=100
export CRATEDB_MCP_MAX_CHARS=50000
```

## Configure HTTP access

Over HTTP, the server requires a bearer token, and refuses to start without one.
```shell
export CRATEDB_MCP_AUTH_TOKEN="$(openssl rand -hex 32)"
```
Clients send it in the `Authorization` header of every request, as
`Authorization: Bearer <token>`. A request without the right token gets
`401 Unauthorized`. For local work only, you can serve without a token.
```shell
export CRATEDB_MCP_AUTH_DISABLED=true
```

The server checks the `Host` and `Origin` headers of every request,
which protects it from DNS rebinding attacks. It answers requests addressed to
`localhost`, `127.0.0.1`, `::1` or the address it listens on. A request
addressed to any other name or IP address gets `421 Misdirected Request`. When
clients reach the server by a name or IP address other than localhost, for
example a service name in Docker Compose, a public host name behind a proxy, or
the IP address of a host that maps a port to the server's container, list them,
separated by spaces.
```shell
export CRATEDB_MCP_ALLOWED_HOSTS="cratedb-mcp mcp.example.org"
```
A browser sends an `Origin` header with its requests. When it does not match the
host it calls, the server answers `403 Forbidden`, unless the origin is listed.
```shell
export CRATEDB_MCP_ALLOWED_ORIGINS="https://app.example.org"
```
The CLI options `--allowed-host` and `--allowed-origin` do the same, and can
be repeated.

The server answers `GET /health` with `OK`, without a token, for liveness probes.

When several instances of the server run behind a load balancer, set
`FASTMCP_STATELESS_HTTP=true` on each of them. Without it, a client on an older
protocol such as 2025-11-25 opens a session on one instance and gets
`404 Session not found` from the others.

## Security considerations

Connect the server with a dedicated database user that holds only what it
needs. Grant it `DQL` on the schemas the model should read, see
[create a read-only database user by using "GRANT DQL"], and limit how long
its statements may run.
```sql
CREATE USER mcp WITH (password = 'YOUR_PASSWORD');
GRANT DQL ON SCHEMA doc TO mcp;
ALTER USER mcp SET (statement_timeout = '30s');
```
CrateDB then stops any statement of that user after 30 seconds. For a remote
cluster, use `https` in the cluster URL.
```shell
export CRATEDB_CLUSTER_URL="https://mcp:YOUR_PASSWORD@example.aks1.westeurope.azure.cratedb.net:4200"
```
When the MCP server is reachable from outside, put it behind a reverse proxy.

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
