from importlib.metadata import PackageNotFoundError, version

__appname__ = "cratedb-mcp"

try:
    __version__ = version(__appname__)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
