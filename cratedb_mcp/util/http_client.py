import contextlib
import http.cookiejar
import socket
import threading
import time
import typing as t

import httpx

TraceCallback = t.Callable[[str, t.Dict[str, t.Any]], None]


def shared_client(**options: t.Any) -> httpx.Client:
    """
    Return an HTTP client for calls that share it. It keeps no cookies, and asks for answers
    without compression, so that a byte limit counts what arrives.
    """
    return httpx.Client(
        cookies=http.cookiejar.CookieJar(http.cookiejar.DefaultCookiePolicy(allowed_domains=[])),
        headers={"Accept-Encoding": "identity"},
        **options,
    )


@contextlib.contextmanager
def shut_down_at(
    deadline: float, connection: socket.socket, abandoned: threading.Event
) -> t.Iterator[None]:
    """
    Shut `connection` down at `deadline`, which ends a read or write that waits on it, and
    set `abandoned`. Once the block is left, the connection is never touched, because the
    client may already serve another call on it.
    """
    lock = threading.Lock()
    watching = True

    def shut_down() -> None:
        with lock, contextlib.suppress(OSError):
            if watching:
                abandoned.set()
                connection.shutdown(socket.SHUT_RDWR)

    timer = threading.Timer(max(0.0, deadline - time.monotonic()), shut_down)
    timer.daemon = True
    timer.start()
    try:
        yield
    finally:
        with lock:
            watching = False
        timer.cancel()


@contextlib.contextmanager
def abandoned_from_connect(deadline: float) -> t.Iterator[t.Tuple[TraceCallback, threading.Event]]:
    """
    Yield a `trace` extension for a request, which shuts each connection the request opens
    down at `deadline`, from its connect on, and the event that says so.
    """
    abandoned = threading.Event()
    with contextlib.ExitStack() as stack:

        def trace(event: str, info: t.Dict[str, t.Any]) -> None:
            if event == "connection.connect_tcp.complete":
                # TLS takes the socket object over, so the deadline shuts down a duplicate.
                connection = info["return_value"].get_extra_info("socket").dup()
                stack.callback(connection.close)
                stack.enter_context(shut_down_at(deadline, connection, abandoned))

        yield trace, abandoned
