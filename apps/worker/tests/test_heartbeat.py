from __future__ import annotations

import json
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from uuid import uuid4

import pytest
from step_by_step_worker.heartbeat import RunTerminal, post_heartbeat


class Recorded:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, str], bytes]] = []
        self.status = 204


class Handler(BaseHTTPRequestHandler):
    recorded: Recorded

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.recorded.requests.append((self.path, dict(self.headers), body))
        self.send_response(self.recorded.status)
        if self.recorded.status == 409:
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"code":"run_terminal","message":"done"}')
            return
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture
def heartbeat_server() -> Iterator[tuple[str, Recorded]]:
    recorded = Recorded()
    handler = type("BoundHandler", (Handler,), {"recorded": recorded})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield f"http://{host}:{port}", recorded
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_post_heartbeat_sends_the_token_and_body(
    heartbeat_server: tuple[str, Recorded], monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, recorded = heartbeat_server
    monkeypatch.setenv("API_URL", origin)
    monkeypatch.setenv("INTERNAL_TOKEN", "shared-token")
    run_id = uuid4()

    post_heartbeat(run_id, "worker-1", "worker-1:5900")

    path, headers, body = recorded.requests[0]
    assert path == f"/internal/runs/{run_id}/heartbeat"
    assert headers["Authorization"] == "Bearer shared-token"
    assert json.loads(body) == {
        "worker_id": "worker-1",
        "vnc_endpoint": "worker-1:5900",
    }


def test_post_heartbeat_raises_when_the_run_is_terminal(
    heartbeat_server: tuple[str, Recorded], monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, recorded = heartbeat_server
    monkeypatch.setenv("API_URL", origin)
    monkeypatch.setenv("INTERNAL_TOKEN", "shared-token")
    recorded.status = 409

    with pytest.raises(RunTerminal):
        post_heartbeat(uuid4(), "worker-1", "worker-1:5900")
