import os
import typing as t
import warnings
from urllib.parse import unquote, urlsplit, urlunsplit

import httpx
from attr.converters import to_bool
from platformdirs import user_cache_dir

from cratedb_mcp import __appname__

DEFAULT_CLUSTER_URL: str = "http://localhost:4200"


T = t.TypeVar("T")


def _env(name: str, default: T, cast: t.Callable[[str], T], positive: bool = False) -> T:
    """
    Read a setting from the environment, falling back to the default value when it is invalid.

    With `positive`, numbers lower than or equal to zero are considered invalid.
    """
    try:
        value = cast(os.getenv(name, str(default)))
        if positive and value <= 0:  # type: ignore[operator]
            raise ValueError(f"{value} is not a positive number")
        return value
    except (ValueError, TypeError) as e:
        warnings.warn(
            f"Environment variable `{name}` invalid: {e}. Using default value: {default}.",
            category=UserWarning,
            stacklevel=3,
        )
        return default


class Settings:
    """
    Application settings bundle.

    All settings are read from the environment when accessed, so they can be
    adjusted at runtime, and mocked in software tests.
    """

    @staticmethod
    def http_timeout(timeout: float = 30.0) -> float:
        """
        Return configured HTTP timeout in seconds.
        """
        return _env("CRATEDB_MCP_HTTP_TIMEOUT", timeout, float, positive=True)

    @staticmethod
    def permit_all_statements() -> bool:
        """
        Whether to permit all statements. By default, only SELECT operations are permitted.
        """
        permitted = _env("CRATEDB_MCP_PERMIT_ALL_STATEMENTS", False, to_bool)
        if permitted:
            warnings.warn(
                "All types of SQL statements are permitted. "
                "This means the LLM agent can write and modify the connected database",
                category=UserWarning,
                stacklevel=2,
            )
        return permitted

    @staticmethod
    def docs_cache_ttl(ttl: int = 3600) -> int:
        """
        Return cache lifetime for documentation resources, in seconds.
        A value of zero disables caching entirely.
        """
        return _env("CRATEDB_MCP_DOCS_CACHE_TTL", ttl, int)

    @staticmethod
    def docs_cache_dir() -> str:
        """
        Return the cache directory for documentation resources.
        """
        return user_cache_dir(appname=__appname__)

    @staticmethod
    def result_max_bytes(max_bytes: int = 1_000_000) -> int:
        """
        Return the maximum size of a single tool result, in bytes.
        """
        return _env("CRATEDB_MCP_RESULT_MAX_BYTES", max_bytes, int, positive=True)

    @staticmethod
    def cluster_url() -> str:
        """
        Return the CrateDB cluster URL, without credentials and without a trailing slash.

        Credentials embedded into `CRATEDB_CLUSTER_URL` are stripped here, and
        re-applied by `cluster_auth`, to keep secrets out of URLs, logs, and
        error messages.
        """
        url = os.getenv("CRATEDB_CLUSTER_URL", DEFAULT_CLUSTER_URL)
        parts = urlsplit(url)
        if parts.username or parts.password:
            netloc = parts.netloc.rpartition("@")[2]
            url = urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
        return url.rstrip("/")

    @staticmethod
    def cluster_auth() -> t.Optional[httpx.Auth]:
        """
        Return basic authentication credentials for the CrateDB cluster.

        Credentials supplied through `CRATEDB_USERNAME` and `CRATEDB_PASSWORD`
        take precedence over credentials embedded into `CRATEDB_CLUSTER_URL`.
        The password is optional, because CrateDB users do not need to have one,
        e.g. the default `crate` superuser, or users authenticated by the `trust` method.
        """
        username = os.getenv("CRATEDB_USERNAME")
        password = os.getenv("CRATEDB_PASSWORD")
        if username:
            return httpx.BasicAuth(username, password or "")
        if password:
            warnings.warn(
                "`CRATEDB_PASSWORD` is ignored, because `CRATEDB_USERNAME` is not set.",
                category=UserWarning,
                stacklevel=2,
            )
        parts = urlsplit(os.getenv("CRATEDB_CLUSTER_URL", DEFAULT_CLUSTER_URL))
        if parts.username:
            return httpx.BasicAuth(unquote(parts.username), unquote(parts.password or ""))
        return None

    @staticmethod
    def cluster_token() -> t.Optional[str]:
        """
        Return the bearer token to authenticate against CrateDB with, if configured.
        """
        return os.getenv("CRATEDB_TOKEN") or None
