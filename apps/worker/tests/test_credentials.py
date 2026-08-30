from __future__ import annotations

import json
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from uuid import uuid4

import pytest
from step_by_step_worker.credentials import HttpCredentials, MissingSecret


class Recorded:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict[str, str], bytes]] = []
        self.status = 200
        self.body = b"{}"
        self.code = "missing_secret"


class Handler(BaseHTTPRequestHandler):
    recorded: Recorded

    def do_GET(self) -> None:
        self._record("GET")
        self._reply()

    def do_POST(self) -> None:
        self._record("POST")
        self._reply()

    def _record(self, method: str) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        self.recorded.requests.append((method, self.path, dict(self.headers), body))

    def _reply(self) -> None:
        self.send_response(self.recorded.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if self.recorded.status == 409:
            self.wfile.write(
                json.dumps(
                    {
                        "code": self.recorded.code,
                        "message": "gone",
                        "variable_names": ["password"],
                    }
                ).encode()
            )
            return
        self.wfile.write(self.recorded.body)

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture
def credential_server() -> Iterator[tuple[str, Recorded]]:
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


def test_fetch_sends_the_token_and_returns_the_resolved_set(
    credential_server: tuple[str, Recorded], monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, recorded = credential_server
    monkeypatch.setenv("API_URL", origin)
    monkeypatch.setenv("INTERNAL_TOKEN", "shared-token")
    recorded.body = json.dumps(
        {
            "secrets": [{"variable_name": "password", "value": "s3cret"}],
            "auth_states": [
                {
                    "domain": "example.com",
                    "cookies": [],
                    "origins": [],
                    "session_storage": [],
                }
            ],
        }
    ).encode()
    run_id = uuid4()

    loaded = HttpCredentials(run_id).fetch()

    method, path, headers, _ = recorded.requests[0]
    assert method == "GET"
    assert path == f"/internal/runs/{run_id}/credentials"
    assert headers["Authorization"] == "Bearer shared-token"
    assert loaded.secrets == {"password": "s3cret"}
    assert next(iter(loaded.auth_states))["domain"] == "example.com"


def test_fetch_raises_missing_secret(
    credential_server: tuple[str, Recorded], monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, recorded = credential_server
    monkeypatch.setenv("API_URL", origin)
    monkeypatch.setenv("INTERNAL_TOKEN", "shared-token")
    recorded.status = 409

    with pytest.raises(MissingSecret) as raised:
        HttpCredentials(uuid4()).fetch()

    assert raised.value.variable_names == ["password"]


def test_consents_and_write_back_use_the_internal_routes(
    credential_server: tuple[str, Recorded], monkeypatch: pytest.MonkeyPatch
) -> None:
    origin, recorded = credential_server
    monkeypatch.setenv("API_URL", origin)
    monkeypatch.setenv("INTERNAL_TOKEN", "shared-token")
    recorded.body = json.dumps({"domains": ["new.test"]}).encode()
    run_id = uuid4()
    client = HttpCredentials(run_id)

    assert client.consents() == ["new.test"]
    client.write_back(
        [
            {
                "domain": "example.com",
                "cookies": [],
                "origins": [],
                "session_storage": [],
            }
        ],
        ["new.test"],
    )

    get_method, get_path, _, _ = recorded.requests[0]
    post_method, post_path, _, post_body = recorded.requests[1]
    assert get_method == "GET"
    assert get_path == f"/internal/runs/{run_id}/auth-state-consents"
    assert post_method == "POST"
    assert post_path == f"/internal/runs/{run_id}/auth-states"
    assert json.loads(post_body) == {
        "states": [
            {
                "domain": "example.com",
                "cookies": [],
                "origins": [],
                "session_storage": [],
            }
        ],
        "new_candidates": ["new.test"],
    }
