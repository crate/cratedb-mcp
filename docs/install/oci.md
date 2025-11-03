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
docker run --rm -it --entrypoint="" ghcr.io/crate/cratedb-mcp cratedb-mcp --version
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
export CRATEDB_CLUSTER_URL=http://crate:crate@cratedb:4200/
```
```shell
docker run --rm --name=cratedb-mcp --network=demo \
  -p 8000:8000 \
  -e CRATEDB_MCP_TRANSPORT -e CRATEDB_MCP_HOST -e CRATEDB_MCP_PORT -e CRATEDB_CLUSTER_URL \
  ghcr.io/crate/cratedb-mcp
```

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
      CRATEDB_CLUSTER_URL: http://crate:crate@cratedb:4200/
```
