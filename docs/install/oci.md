:::{include} ../_links.md
:::

(install-oci)=

# CrateDB MCP OCI

:::{div}
OCI images for Docker or Podman are available on GHCR per [CrateDB MCP server OCI images].
There is a standard OCI image and an MCPO image suitable for Open WebUI.

See also [Docker Hub MCP Server] and [mcp hub].
:::

## OCI image

Image name.
```text
ghcr.io/crate/cratedb-mcp
```

Probe invocation.
```shell
docker run --rm -it --entrypoint="" ghcr.io/crate/cratedb-mcp:latest cratedb-mcp --version
```

## Usage

Run CrateDB database.
```shell
docker network create demo
```
```shell
docker run --rm --name=cratedb --network=demo \
  -p 4200:4200 -p 5432:5432 \
  -e CRATE_HEAP_SIZE=2g \
  crate:latest -Cdiscovery.type=single-node
```

Configure and run CrateDB MCP server.
```shell
export CRATEDB_MCP_TRANSPORT=streamable-http
export CRATEDB_MCP_HOST=0.0.0.0
export CRATEDB_MCP_PORT=8000
export CRATEDB_MCP_AUTH_TOKEN=YOUR_TOKEN
export CRATEDB_CLUSTER_URL=http://crate:crate@testcluster.cratedb.net:4200/
```
```shell
docker run --rm --name=cratedb-mcp --network=demo \
  -p 8000:8000 \
  -e CRATEDB_MCP_TRANSPORT -e CRATEDB_MCP_HOST -e CRATEDB_MCP_PORT \
  -e CRATEDB_MCP_AUTH_TOKEN -e CRATEDB_CLUSTER_URL \
  ghcr.io/crate/cratedb-mcp:latest
```

:::{note}
When listening on a non-loopback address like `0.0.0.0`, the server requires
`CRATEDB_MCP_AUTH_TOKEN`, and refuses to start without it. The token is a
secret you generate yourself, e.g. using `openssl rand -hex 32`, and share
with your MCP clients like an API key. They must present it as
`Authorization: Bearer YOUR_TOKEN`. It is a single shared secret without
per-user identity, and needs TLS in front of the server when exposed beyond
a trusted network, see [](#configure) for details and limitations.

Clients connecting through `localhost` work out of the box. When clients
address the server by another hostname, e.g. the container name or a public
DNS name, announce it using `CRATEDB_MCP_ALLOWED_HOSTS`, otherwise requests
are rejected with HTTP 421. Browser-based clients also need their origin
within `CRATEDB_MCP_ALLOWED_ORIGINS`. Both accept multiple values, separated
by whitespace. See also [](#configure).
:::

## GitHub Actions

If you need instances of CrateDB and CrateDB MCP on a CI environment on GitHub Actions,
using this section might be handy, as it includes all relevant configuration options
in one go.
```yaml
services:

  cratedb:
    image: crate/crate:latest
    ports:
      - 4200:4200
      - 5432:5432
    env:
      CRATE_HEAP_SIZE: 2g

  cratedb-mcp:
    image: ghcr.io/crate/cratedb-mcp:latest
    ports:
      - 8000:8000
    env:
      CRATEDB_MCP_TRANSPORT: streamable-http
      CRATEDB_MCP_HOST: 0.0.0.0
      CRATEDB_MCP_PORT: 8000
      CRATEDB_MCP_AUTH_TOKEN: ${{ secrets.CRATEDB_MCP_AUTH_TOKEN }}
      CRATEDB_MCP_ALLOWED_HOSTS: cratedb-mcp
      CRATEDB_CLUSTER_URL: http://crate:crate@testcluster.cratedb.net:4200/
```
