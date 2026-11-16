import http.cookiejar
import typing as t

import httpx


def shared_client(**options: t.Any) -> httpx.Client:
    """
    Return an HTTP client for calls that share it. It keeps no cookies.
    """
    return httpx.Client(
        cookies=http.cookiejar.CookieJar(http.cookiejar.DefaultCookiePolicy(allowed_domains=[])),
        **options,
    )
