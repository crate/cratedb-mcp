import os
import warnings

HTTP_URL: str = os.getenv("CRATEDB_MCP_HTTP_URL", "http://localhost:4200")

# Configure cache lifetime for documentation resources.
DOCS_CACHE_TTL: int = 3600
try:
    DOCS_CACHE_TTL = int(os.getenv("CRATEDB_MCP_DOCS_CACHE_TTL", DOCS_CACHE_TTL))
except ValueError as e:  # pragma: no cover
    # If the environment variable is not a valid integer, use the default value, but warn about it.
    # TODO: Add software test after refactoring away from module scope.
    warnings.warn(f"Environment variable `CRATEDB_MCP_DOCS_CACHE_TTL` invalid: {e}. "
                  f"Using default value: {DOCS_CACHE_TTL}.", category=UserWarning, stacklevel=2)

# Configure HTTP timeout for all conversations.
HTTP_TIMEOUT = 10.0
