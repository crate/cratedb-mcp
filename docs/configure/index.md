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
in seconds. `fetch_cratedb_docs` ends each call within this time, the redirects
of the page included, once a connection to the site stands. Finding the site takes
as long as the system's name lookup, and connecting to it up to this time for each
address its name resolves to.

The `CRATEDB_MCP_DOCS_CACHE_TTL` environment variable (default: 3600) defines
the cache lifetime for documentation resources in seconds. The server keeps the
documentation pages it fetched in memory for that long, at most 200 pages and 16 MB,
and in no file.

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

## Configure result size

Every row `query_sql` returns lands in the model's context, so results are cut.
By default a result holds at most 100 rows and 50,000 characters of rows. The
model can ask for up to 1,000 rows with the `max_rows` argument, or up to the
configured row cap when it is larger. Both caps also
bound what `get_cluster_health` returns. The character cap alone bounds the pages
`get_cratedb_documentation_index` lists and the page text `fetch_cratedb_docs`
returns. When an answer is cut, it says so in `truncated` and
explains why in `note`. A longer documentation page comes in parts, and the `note`
of each part names the `start` argument that reads the next one.
```shell
export CRATEDB_MCP_MAX_ROWS=100
export CRATEDB_MCP_MAX_CHARS=50000
```
The server does not start when either cap is not a whole number above zero, or when
`CRATEDB_MCP_HTTP_TIMEOUT` is not a number above zero.

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
A call with any other statement fails, unless the
`CRATEDB_MCP_PERMIT_ALL_STATEMENTS` environment variable is set to a
truthy value.

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
