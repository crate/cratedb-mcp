import asyncio
import os
import socket
import threading
import time

import httpcore
import pytest
from fastmcp import Client

from cratedb_mcp import tool
from cratedb_mcp.core import CrateDbMcp
from cratedb_mcp.knowledge import DocumentationIndex

SITE = "https://docs.cratedb.com/projects/guide/"
PAGE = b"a page"


def respond(connection, status, headers, body=b""):
    head = f"HTTP/1.1 {status}\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items())
    connection.sendall(head.encode() + b"\r\n" + body)


class LocalSite:
    """
    A local HTTP server that every documentation request reaches, without TLS, whatever
    address it names, and through a proxy when one is configured. The last part of the path
    chooses the answer, and `open` counts the connections the server still holds.
    """

    def __init__(self) -> None:
        self.server = socket.create_server(("127.0.0.1", 0))
        self.port = self.server.getsockname()[1]
        self.open = 0
        self.lock = threading.Lock()
        threading.Thread(target=self.accept, daemon=True).start()

    def accept(self) -> None:
        while True:
            try:
                connection, _ = self.server.accept()
            except OSError:
                return
            with self.lock:
                self.open += 1
            threading.Thread(target=self.serve, args=(connection,), daemon=True).start()

    def serve(self, connection: socket.socket) -> None:
        try:
            with connection:
                head = b""
                while True:
                    chunk = connection.recv(65_536)
                    if not chunk:
                        return
                    head += chunk
                    if b"\r\n\r\n" in head:
                        method, path = head.decode().split(" ")[:2]
                        head = b""
                        if method == "CONNECT":
                            respond(connection, "200 Connection established", {})
                        elif not self.answer(connection, path.rsplit("/", 1)[-1]):
                            return
        except OSError:
            pass
        finally:
            with self.lock:
                self.open -= 1

    def answer(self, connection: socket.socket, name: str) -> bool:
        """Answer the request for `name`, and say whether the connection serves another."""
        if name == "page":
            respond(connection, "200 OK", {"Content-Type": "text/plain", "Content-Length": 6}, PAGE)
        elif name == "missing":
            respond(connection, "404 Not Found", {"Content-Length": 4}, b"gone")
        elif name == "moved":
            respond(
                connection,
                "302 Found",
                {"Location": "https://example.org/", "Content-Length": 5},
                b"moved",
            )
        elif name == "binary":
            respond(
                connection, "200 OK", {"Content-Type": "image/png", "Content-Length": 4}, b"\x89PNG"
            )
        elif name == "large":
            respond(
                connection, "200 OK", {"Content-Type": "text/plain", "Content-Length": 50_000_000}
            )
            while True:
                connection.sendall(b"x" * 65_536)
        elif name == "stall":
            connection.recv(1)
        elif name == "trickle":
            respond(connection, "200 OK", {"Content-Type": "text/plain", "Content-Length": 20})
            for _ in range(20):
                time.sleep(0.2)
                connection.sendall(b"x")
        elif name == "slow-head":
            connection.sendall(b"HTTP/1.1 200 OK\r\nX-Slow: ")
            while True:
                time.sleep(0.1)
                connection.sendall(b"x")
        elif name == "interim":
            while True:
                time.sleep(0.1)
                connection.sendall(b"HTTP/1.1 103 Early Hints\r\n\r\n")
        return name in ("page", "missing", "moved", "binary")

    def refuse_connections(self) -> None:
        """Send every request to a port where nothing listens."""
        with socket.socket() as unused:
            unused.bind(("127.0.0.1", 0))
            self.port = unused.getsockname()[1]


@pytest.fixture
def local_site(mocker):
    site = LocalSite()
    connect_tcp = httpcore.SyncBackend.connect_tcp

    def connect_locally(backend, host, port, timeout=None, local_address=None, socket_options=None):
        stream = connect_tcp(
            backend, "127.0.0.1", site.port, timeout, local_address, socket_options
        )
        stream.start_tls = lambda *args, **kwargs: stream
        return stream

    mocker.patch.object(httpcore.SyncBackend, "connect_tcp", connect_locally)
    mocker.patch.object(tool, "documentation_index", DocumentationIndex())
    yield site
    site.server.close()


def within(seconds, scenario):
    """Return what the coroutine function `scenario` returns, and fail when it takes longer."""
    outcome = {}

    def run():
        try:
            outcome["result"] = asyncio.run(scenario())
        except BaseException as e:
            outcome["error"] = e

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(seconds)
    if "error" in outcome:
        raise outcome["error"]
    assert "result" in outcome, f"no answer within {seconds} seconds"
    return outcome["result"]


async def fetch(client, name):
    started = time.monotonic()
    result = await client.call_tool(
        "fetch_cratedb_docs", {"link": SITE + name}, raise_on_error=False
    )
    text = result.content[0].text
    return result.is_error, text, time.monotonic() - started


def test_calls_that_end_without_reading_the_body_leave_no_connection_open(local_site):
    kinds = ["missing", "moved", "binary", "large"]

    async def scenario():
        async with Client(CrateDbMcp().mcp) as client:
            failed = [(await fetch(client, kinds[n % 4]))[0] for n in range(150)]
            return failed, await fetch(client, "page")

    failed, page = within(30, scenario)
    assert failed == [True] * 150
    assert page[:2] == (False, PAGE.decode())
    for _ in range(100):
        if local_site.open == 0:
            break
        time.sleep(0.02)
    assert local_site.open == 0


@pytest.mark.parametrize("name", ["stall", "trickle", "slow-head", "interim"])
def test_page_that_does_not_arrive_ends_at_the_deadline_while_other_calls_go_on(
    local_site, mocker, name
):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_HTTP_TIMEOUT": "1"})

    async def scenario():
        async with Client(CrateDbMcp().mcp) as client:
            late = asyncio.create_task(fetch(client, name))
            await asyncio.sleep(0.3)
            return await fetch(client, "page"), await late

    page, late = within(10, scenario)
    assert page[:2] == (False, PAGE.decode())
    assert page[2] < 0.5
    assert late[:2] == (True, "The page did not arrive within the 1-second timeout.")
    assert late[2] < 1.5


def test_refused_connection_says_the_site_cannot_be_reached(local_site):
    local_site.refuse_connections()

    async def scenario():
        async with Client(CrateDbMcp().mcp) as client:
            return await fetch(client, "page")

    assert within(10, scenario)[:2] == (True, "The site of the page cannot be reached.")
