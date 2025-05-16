import os
import warnings

from attr.converters import to_bool

HTTP_URL: str = os.getenv("CRATEDB_MCP_HTTP_URL", "http://localhost:4200")

# Configure HTTP timeout for all conversations.
HTTP_TIMEOUT = 10.0

# Whether to permit all statements. By default, only SELECT operations are permitted.
PERMIT_ALL_STATEMENTS: bool = to_bool(os.getenv("CRATEDB_MCP_PERMIT_ALL_STATEMENTS", "false"))

# TODO: Refactor into code which is not on the module level. Use OOM early.
if PERMIT_ALL_STATEMENTS:  # pragma: no cover
    warnings.warn("All types of SQL statements are permitted. This means the LLM "
                  "agent can write and modify the connected database", category=UserWarning, stacklevel=2)


class Settings:
    """
    Bundle application settings.
    """

    @staticmethod
    def docs_cache_ttl(ttl: int = 3600) -> int:
        """
        Return cache lifetime for documentation resources, in seconds.
        """
        try:
            return int(os.getenv("CRATEDB_MCP_DOCS_CACHE_TTL", ttl))
        except ValueError as e:  # pragma: no cover
            # If the environment variable is not a valid integer, use the default value, but warn about it.
            # TODO: Add software test after refactoring away from module scope.
            warnings.warn(f"Environment variable `CRATEDB_MCP_DOCS_CACHE_TTL` invalid: {e}. "
                          f"Using default value: {ttl}.", category=UserWarning, stacklevel=2)
            return ttl
