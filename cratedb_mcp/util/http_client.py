import typing as t

import httpx


def uncompressed_client() -> httpx.Client:
    """
    Return an HTTP client that asks for answers without compression, so that a byte limit
    counts what arrives.
    """
    return httpx.Client(headers={"Accept-Encoding": "identity"})


def read_at_most(response: httpx.Response, limit: int) -> t.Optional[bytearray]:
    """Return the body of `response`, or None as soon as it announces or passes `limit` bytes."""
    if int(response.headers.get("content-length") or 0) > limit:
        return None
    body = bytearray()
    for chunk in response.iter_bytes():
        body += chunk
        if len(body) > limit:
            return None
    return body
