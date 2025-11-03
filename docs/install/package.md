(install-package)=

# Package

The configuration snippets for AI assistants are using the `uvx` launcher
provided by the [uv] package manager to start the application after installing it,
like the `npx` launcher is doing it for JavaScript and TypeScript applications.
This section uses `uv tool install` to install the application persistently.

```shell
uv tool install --upgrade cratedb-mcp
```

:::{note}
- We recommend using the [uv] package manager to install the `cratedb-mcp`
  package, like many other MCP servers are doing it.
  ```shell
  {apt,brew,pipx,zypper} install uv
  ```
- We recommend using `uv tool install` to install the program "user"-wide
  into your environment so you can invoke the program `cratedb-mcp` from
  anywhere across your terminal
  sessions or MCP client programs / AI assistants.
- If you are unable to use `uv tool install`, you can use `uvx cratedb-mcp`
  to acquire the package and run the application ephemerally.
:::


[uv]: https://docs.astral.sh/uv/
