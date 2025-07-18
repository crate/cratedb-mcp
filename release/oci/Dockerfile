# Stage 1: Build wheel package
FROM python:3.13-slim-bookworm AS build

ARG BUILD=/usr/src

# Configure operating system.
ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=linux
ENV PIP_ROOT_USER_ACTION=ignore

# Install prerequisites.
RUN apt-get update
RUN apt-get --yes install --no-install-recommends --no-install-suggests git
RUN pip install build

COPY . ${BUILD}
RUN python -m build --wheel ${BUILD}


FROM python:3.13-slim-bookworm AS standard

# Configure operating system.
ENV DEBIAN_FRONTEND=noninteractive
ENV TERM=linux

# Install and configure `uv`.
# Guidelines that have been followed.
# - https://hynek.me/articles/docker-uv/

# Install the `uv` package manager.
# Security-conscious organizations should package/review uv themselves.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# - Tell uv to byte-compile packages for faster application startups.
# - Silence uv complaining about not being able to use hard links.
# - Prevent uv from accidentally downloading isolated Python builds.
# - Install packages into the system Python environment.
ENV \
    UV_COMPILE_BYTECODE=true \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_SYSTEM_PYTHON=true

# Configure runtime environment.
ENV PATH=/root/.local/bin:$PATH

ARG BUILD=/usr/src

# Provide wheel package.
COPY --from=build ${BUILD}/dist/*.whl /tmp

# Install package.
RUN \
    --mount=type=cache,id=pip,target=/root/.cache/pip \
    --mount=type=cache,id=uv,target=/root/.cache/uv \
    true \
    && uv pip install --upgrade "$(ls /tmp/*.whl)"

# Copy `selftest.sh` to the image.
COPY release/oci/selftest.sh /usr/local/bin

# Standard MCP server.
# Specify the command to run the MCP server.
ENTRYPOINT ["cratedb-mcp", "serve", "--transport=stdio"]


FROM standard AS mcpo
# MCP support for Open WebUI.
# https://docs.openwebui.com/openapi-servers/mcp/
# https://github.com/open-webui/mcpo
RUN uv pip install mcpo
ENTRYPOINT []
CMD ["mcpo", "--host", "0.0.0.0", "--port", "8000", "--", "cratedb-mcp", "serve", "--transport=stdio"]
