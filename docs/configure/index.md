:::{include} ../_links.md
:::

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
The server reads the address when it starts, and does not start when it is not an
`http` or `https` URL with a host. A user name or password that holds characters
such as `/`, `#`, `?` or `@` must be percent-encoded, such as `/` as `%2F`.

The `CRATEDB_MCP_HTTP_TIMEOUT` environment variable (default: 30.0) defines
the timeout for HTTP requests to CrateDB and its documentation resources
in seconds.

The `CRATEDB_MCP_DOCS_CACHE_TTL` environment variable (default: 3600) defines
the cache lifetime for documentation resources in seconds. The server keeps the
documentation pages it fetched in memory for that long, up to 16 million characters
of text, and in no file.

## Configure transport

MCP servers can be started using different transport modes. The default transport
is `stdio`, you can select `http` instead. Over HTTP, the server requires a
bearer token, see [Configure HTTP access](#configure-http-access).
```shell
export CRATEDB_MCP_AUTH_TOKEN="$(openssl rand -hex 32)"
cratedb-mcp serve --transport=http
```
NB: The `http` transport was called `streamable-http` in earlier spec iterations.
The `sse` transport is deprecated, as it is in the MCP specification.

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
By default a result holds at most 1,000 rows and 50,000 characters of rows, and
`rows_returned` says how many rows it holds. The model can ask for fewer rows with
the `limit` argument, never for more. Both caps also
bound what `list_schemas`, `list_tables` and `get_cluster_health` return. The
character cap alone bounds the plans
`explain_query` returns and the definition `describe_table` returns. When an
answer is cut, it says so in `truncated` and explains why in `note`.
```shell
export CRATEDB_MCP_MAX_ROWS=1000
export CRATEDB_MCP_MAX_CHARS=50000
```
The server does not start when either cap is not a whole number above zero, or when
`CRATEDB_MCP_HTTP_TIMEOUT` is not a number above zero.

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

## Security considerations

:::{div}
Connect the server with a dedicated database user that holds only what it
needs. Grant it `DQL` on the schemas the model should read, see
[create a read-only database user by using "GRANT DQL"], and limit how long
its statements may run.
:::
```sql
CREATE USER mcp WITH (password = 'YOUR_PASSWORD');
GRANT DQL ON SCHEMA doc TO mcp;
ALTER USER mcp SET (statement_timeout = '30s');
```
CrateDB then stops any statement of that user after 30 seconds.

Each tool needs the rights below. The last column shows what it returns when the
user holds `DQL` on single schemas only, as in the example.

| Tool | Needs | With `DQL` on single schemas |
|---|---|---|
| `query_sql` | `DQL` on the tables it queries | Rows of those tables. For any other table, CrateDB's error, such as `Schema 'sys' unknown` |
| `explain_query` | `DQL` on the tables it explains | Plans for those tables, also with `analyze`. For any other table, CrateDB's error |
| `list_schemas` | `DQL` on a schema, to list it | Only those schemas, also with `include_system` |
| `list_tables` | `DQL` on the schema | The tables and views of those schemas, and none for any other schema |
| `describe_table` | `DQL` on the table, and on `sys` for its shard, record, size and partition counts | The definition, without the counts, and a note that says so. A table in any other schema is not found |
| `get_cratedb_documentation_index` | No right on the database | The documentation index |
| `fetch_cratedb_docs` | No right on the database | The documentation page |
| `get_cluster_health` | `DQL` on `sys` | CrateDB's error `Schema 'sys' unknown` |

For a remote cluster, use `https` in the cluster URL.
```shell
export CRATEDB_CLUSTER_URL="https://mcp:YOUR_PASSWORD@example.aks1.westeurope.azure.cratedb.net:4200"
```
When the MCP server is reachable from outside, put it behind a reverse proxy.

The MCP Server also permits only read statements on the application level:
one `SELECT`, `WITH`, `VALUES` or `SHOW` statement per call, or an `EXPLAIN`
of a `SELECT`, `WITH` or `VALUES` statement. A call with any other statement,
`COPY` included, fails, unless the `CRATEDB_MCP_PERMIT_ALL_STATEMENTS`
environment variable is set to a truthy value. The check also fails a statement
it cannot analyze: one with more than 10,000 tokens in a list or clause, such as a
very long `IN (...)` list, or nested more than 100 levels deep. The error names the
limit, and the server sends no such statement to CrateDB.

## System prompt customizations

The CrateDB MCP server sends a short built-in instructions text to every client
when it connects. The text says what the server is, and lists the differences
between CrateDB and PostgreSQL that cause wrong or slow answers. It sets no persona.
Users can adjust it by either redefining the baseline instructions or extending
them with custom conventions.
Additional conventions can capture domain-specific details, such as information
required for particular ER data models, or any other guidelines you develop
over time.

If you want to **add** custom conventions to the system prompt,
use the `--conventions` option.
```shell
cratedb-mcp serve --conventions="conventions-custom.md"
```

If you want to **replace** the built-in instructions text completely,
use the `--instructions` option.
```shell
cratedb-mcp serve --instructions="instructions-custom.md"
```

Alternatively, use the `CRATEDB_MCP_INSTRUCTIONS` and `CRATEDB_MCP_CONVENTIONS`
environment variables instead of the CLI options.

To retrieve the built-in instructions text, use the `show-prompt` subcommand. By
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
