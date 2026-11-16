import functools
import math
import os
import typing as t
import warnings

import httpx
from attr.converters import to_bool


class InvalidSetting(ValueError):
    """A setting holds a value the server cannot use."""


def parse_cluster_url(address: str) -> httpx.URL:
    """
    Parse the address of the CrateDB cluster. A refusal names what is wrong in general
    terms only, because the address may hold a password.
    """
    fault: t.Optional[str] = None
    try:
        url = httpx.URL(address)
    except httpx.InvalidURL as e:
        port = str(e).startswith("Invalid port")
        fault = "its port is not a number" if port else "it is not a valid URL"
    else:
        if url.scheme not in ("http", "https"):
            fault = "it does not start with http:// or https://"
        elif not url.host:
            fault = "it names no host"
        elif url.port is not None and url.port > 65535:
            fault = "its port is above 65535"
        elif "@" in address and not url.userinfo:
            fault = "it holds an @ outside the user name and password"
        elif url.query or url.fragment:
            fault = "it holds a query (?) or a fragment (#)"
    if fault:
        raise InvalidSetting(
            f"CRATEDB_CLUSTER_URL cannot be used, because {fault}. A user name or password "
            "with characters such as /, #, ? or @ must be percent-encoded, such as / as %2F."
        )
    return url


POSITIVE_NUMBERS = {
    "CRATEDB_MCP_MAX_ROWS": int,
    "CRATEDB_MCP_MAX_CHARS": int,
    "CRATEDB_MCP_HTTP_TIMEOUT": float,
}


def check_positive_numbers() -> None:
    """Refuse a row cap, character cap or HTTP timeout that is not a number above zero."""
    for name, kind in POSITIVE_NUMBERS.items():
        value = os.getenv(name)
        if value is None:
            continue
        try:
            number = kind(value)
        except ValueError:
            fault = "it is not a whole number" if kind is int else "it is not a number"
        else:
            if math.isnan(number):
                fault = "it is not a number"
            elif math.isinf(number):
                fault = "it is infinite"
            elif number <= 0:
                fault = "it is zero or negative"
            else:
                continue
        raise InvalidSetting(f"{name} cannot be used, because {fault}.")


class Settings:
    """
    Application settings bundle.
    """

    @staticmethod
    @functools.cache
    def cluster_url() -> httpx.URL:
        """
        Return the address of the CrateDB cluster from `CRATEDB_CLUSTER_URL`, parsed once.
        """
        return parse_cluster_url(os.getenv("CRATEDB_CLUSTER_URL", "http://localhost:4200"))

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

    @staticmethod
    def max_rows(rows: int = 100) -> int:
        """
        Return the row cap of the tools that cut their answers by rows.
        """
        try:
            return int(os.getenv("CRATEDB_MCP_MAX_ROWS", rows))
        except ValueError as e:
            warnings.warn(
                f"Environment variable `CRATEDB_MCP_MAX_ROWS` invalid: {e}. "
                f"Using default value: {rows}.",
                category=UserWarning,
                stacklevel=2,
            )
            return rows

    @staticmethod
    def max_chars(chars: int = 50_000) -> int:
        """
        Return the character cap of the tools that cut their answers.
        """
        try:
            return int(os.getenv("CRATEDB_MCP_MAX_CHARS", chars))
        except ValueError as e:
            warnings.warn(
                f"Environment variable `CRATEDB_MCP_MAX_CHARS` invalid: {e}. "
                f"Using default value: {chars}.",
                category=UserWarning,
                stacklevel=2,
            )
            return chars
