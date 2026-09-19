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

The `CRATEDB_MCP_RESULT_MAX_BYTES` environment variable (default: 1000000)
defines the maximum size of a single tool result in bytes. Larger results are
rejected while still being received, with a hint to refine the query, instead
of exhausting server memory or flooding the context window of the AI assistant.

The `CRATEDB_MCP_DOCS_CACHE_TTL` environment variable (default: 3600) defines
the cache lifetime for documentation resources in seconds. A value of zero
disables caching. The cache is stored within the platform-specific user cache
directory, and is bypassed automatically when that location is not writable.

Instead of embedding credentials into `CRATEDB_CLUSTER_URL`, you can also use
the `CRATEDB_USERNAME` and `CRATEDB_PASSWORD` environment variables for basic
authentication, or `CRATEDB_TOKEN` for bearer token (JWT) authentication.
The password is optional, for CrateDB users which do not have one.
Use an `https://` cluster URL when connecting to a remote cluster, otherwise
credentials travel unencrypted, and the server warns about it on startup.

## Configure transport

MCP servers can be started using different transport modes. The default transport
is `stdio`, you can select another one of `{"stdio", "http", "streamable-http"}`
and supply it to the invocation like this:
```shell
cratedb-mcp serve --transport=stdio
```
NB: The `http` transport was called `streamable-http` in earlier spec iterations.

When using any of the HTTP-based options for serving the MCP interface, you can
use the CLI options `--host`, `--port` and `--path` to specify the listening address.
The default values are `localhost:8000`, where the HTTP server responds to
`/mcp/` by default. The deprecated `sse` transport is not offered, because its
FastMCP implementation does not validate the `Host` and `Origin` headers.

Alternatively, you can use environment variables instead of CLI options.
```shell
export CRATEDB_MCP_TRANSPORT=http
export CRATEDB_MCP_HOST=0.0.0.0
export CRATEDB_MCP_PORT=8000
```
```shell
export CRATEDB_MCP_PATH=/path/in/url
```

## Secure the HTTP transports

The HTTP-based transports accept requests from anywhere the server is
reachable, so they are protected in two ways.

**Client authentication.** Configure a bearer token that MCP clients must
present. The server refuses to listen on a non-loopback address without
one. Prefer the environment variable over the `--auth-token` command line
option, because command line arguments are visible in the process list.

The token is not issued by any service, it is a secret you generate yourself,
and share with the people or tools connecting to the server, like an API key.
```shell
export CRATEDB_MCP_AUTH_TOKEN=$(openssl rand -hex 32)
cratedb-mcp serve --transport=http --host=0.0.0.0
```
MCP clients present it using the `Authorization` header. How to configure
that depends on the client, many accept a `headers` section like this one.
```json
{
  "mcpServers": {
    "cratedb": {
      "url": "https://mcp.example.com/mcp",
      "headers": {"Authorization": "Bearer YOUR_TOKEN"}
    }
  }
}
```
Please be aware of the limitations of this scheme.

- It is a single shared secret. The server can not tell clients apart, so
  there is no per-user identity, and revoking access for one client means
  rotating the token for all of them, by restarting the server.
- The token is transmitted with each request. When exposing the server beyond
  a trusted network, terminate TLS in front of it, otherwise the token can be
  intercepted.
- Clients which support OAuth only, e.g. some hosted connectors, can not
  present a static token.

It keeps anonymous clients out, it is not a user authentication system. For
multi-user deployments, authenticate users at a reverse proxy or gateway
connected to your identity provider, and use the token, or the escape hatch
`--allow-unauthenticated` together with network-level protection, only for
the hop between that gateway and the MCP server.

**Host and origin validation.** The server rejects requests with an unexpected
`Host` header (HTTP 421) or a foreign browser `Origin` (HTTP 403), which
mitigates DNS rebinding attacks against locally bound servers. When running
behind a reverse proxy or on a public hostname, announce that hostname, and
the origin used by browser-based MCP clients.
```shell
cratedb-mcp serve --transport=http --host=0.0.0.0 \
  --allowed-host=mcp.example.com \
  --allowed-origin=https://mcp.example.com
```
For deployments configured through the environment, e.g. containers, use the
`CRATEDB_MCP_ALLOWED_HOSTS` and `CRATEDB_MCP_ALLOWED_ORIGINS` environment
variables, which accept multiple values separated by whitespace, and
`CRATEDB_MCP_ALLOW_UNAUTHENTICATED`.

On startup, the server reports the connectivity to the CrateDB cluster. Use
`--no-check-cluster` to skip that check.

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
:::{warning}
**The database user is the enforcement boundary.** The MCP Server additionally
denies write statements on the application level, but that filter is a
convenience layer only, it must not be relied upon as a security control.
:::

The application-level filter permits the read-only statements `SELECT`
(including common table expressions), `EXPLAIN` for read-only statements, and
`SHOW`. Multiple statements per request, and write statements hidden behind a
read-only statement, are rejected. All other operations raise a
`PermissionError` exception, unless the `CRATEDB_MCP_PERMIT_ALL_STATEMENTS`
environment variable is set to a truthy value, which disables the filter
altogether, and emits a warning on startup.

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
