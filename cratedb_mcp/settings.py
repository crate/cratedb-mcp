import os
import warnings

from attr.converters import to_bool

HTTP_URL: str = os.getenv("CRATEDB_CLUSTER_URL", "http://localhost:4200")


class Settings:
    """
    Application settings bundle.
    """

    @staticmethod
    def http_timeout(timeout: float = 30.0) -> float:
        """
        Return configured HTTP timeout in seconds.
        """
        try:
            return float(os.getenv("CRATEDB_MCP_HTTP_TIMEOUT", timeout))
        except ValueError as e:  # pragma: no cover
            # If the environment variable is not a valid float,
            # use the default value, but warn about it.
            # TODO: Add software test after refactoring away from module scope.
            warnings.warn(
                f"Environment variable `CRATEDB_MCP_HTTP_TIMEOUT` invalid: {e}. "
                f"Using default value: {timeout}.",
                category=UserWarning,
                stacklevel=2,
            )
            return timeout

    @staticmethod
    def permit_all_statements() -> bool:
        """
        Whether to permit all statements. By default, only SELECT operations are permitted.
        """
        permitted = False
        try:
            permitted = to_bool(os.getenv("CRATEDB_MCP_PERMIT_ALL_STATEMENTS", "false"))
            if permitted:
                warnings.warn(
                    "All types of SQL statements are permitted. "
                    "This means the LLM agent can write and modify the connected database",
                    category=UserWarning,
                    stacklevel=2,
                )
        except (ValueError, TypeError) as e:
            # If the environment variable is not a valid integer,
            # use the default value, but warn about it.
            # TODO: Add software test after refactoring away from module scope.
            warnings.warn(
                f"Environment variable `CRATEDB_MCP_PERMIT_ALL_STATEMENTS` invalid: {e}. ",
                category=UserWarning,
                stacklevel=2,
            )
        return permitted

    @staticmethod
    def docs_cache_ttl(ttl: int = 3600) -> int:
        """
        Return cache lifetime for documentation resources, in seconds.
        """
        try:
            return int(os.getenv("CRATEDB_MCP_DOCS_CACHE_TTL", ttl))
        except ValueError as e:  # pragma: no cover
            # If the environment variable is not a valid integer,
            # use the default value, but warn about it.
            # TODO: Add software test after refactoring away from module scope.
            warnings.warn(
                f"Environment variable `CRATEDB_MCP_DOCS_CACHE_TTL` invalid: {e}. "
                f"Using default value: {ttl}.",
                category=UserWarning,
                stacklevel=2,
            )
            return ttl
