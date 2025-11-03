(install)=

# Installation

::::{grid} 2 2 2 2
:gutter: 2

:::{grid-item-card} {octicon}`package;2em` &nbsp; Package
:link: install-package
:link-type: ref
+++
Install the `cratedb-mcp` package using `pipx` or `uv`,
suitable for running as standalone service.
:::

:::{grid-item-card} {material-outlined}`integration_instructions;2em` &nbsp; Integrate
:link: integrate
:link-type: ref
+++
Integrate CrateDB MCP with standard AI applications
like Claude, Cline, Cursor, Roo Code, or Windsurf.
:::

:::{grid-item-card} {octicon}`container;2em` &nbsp; OCI
:link: install-oci
:link-type: ref
+++
OCI images for Docker or Podman are available on GHCR.

Image: `ghcr.io/crate/cratedb-mcp`
:::

:::{grid-item-card} {octicon}`star;2em` &nbsp; MCPO
:link: install-mcpo
:link-type: ref
+++
The CrateDB MCPO OCI image supports Open WebUI out of the box.

Image: `ghcr.io/crate/cratedb-mcpo`
:::

::::

:::{toctree}
:caption: Get started
:maxdepth: 1
:hidden:

package
integrate
OCI <oci>
MCPO <mcpo>
:::
