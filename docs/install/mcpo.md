:::{include} ../_links.md
:::

(install-mcpo)=

# CrateDB MCPO

:::{div}
OCI images for Docker or Podman are available on GHCR per [CrateDB MCP server OCI images].
There is a standard OCI image and an MCPO image suitable for Open WebUI.

For integrating Open WebUI, the project provides an OCI MCPO image which wraps
the MCP server using the `mcpo` proxy. See also [MCP support for Open WebUI] and
[MCP-to-OpenAPI proxy server (mcpo)].
:::

## OCI image

Image name.
```text
ghcr.io/crate/cratedb-mcpo
```

Invoke the CrateDB MCPO server for Open WebUI.
```shell
docker run --rm --name=cratedb-mcpo --network=demo \
  -p 8000:8000 \
  -e CRATEDB_CLUSTER_URL ghcr.io/crate/cratedb-mcpo
```
