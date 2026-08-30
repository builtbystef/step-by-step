"""A tiny RFB 3.8 server that records which password authenticated."""

from __future__ import annotations

import secrets
import socket
import threading
from dataclasses import dataclass, field

from step_by_step_api.runs.rfb import RFB_VERSION, SECURITY_VNC, vnc_response

_PIXEL_FORMAT = bytes(
    [
        32,
        24,
        0,
        1,
        0,
        255,
        0,
        255,
        0,
        255,
        16,
        8,
        0,
        0,
        0,
        0,
    ]
)
_SERVER_INIT = (
    (1).to_bytes(2, "big")
    + (1).to_bytes(2, "big")
    + _PIXEL_FORMAT
    + (4).to_bytes(4, "big")
    + b"test"
)
_FRAMEBUFFER_UPDATE = (
    b"\x00\x00"
    + (1).to_bytes(2, "big")
    + (0).to_bytes(2, "big") * 2
    + (1).to_bytes(2, "big") * 2
    + (0).to_bytes(4, "big")
    + b"\x00\x00\x00\xff"
)


@dataclass
class VncClient:
    """One accepted TCP connection to the fake Worker."""

    password_used: str | None = None
    seen_keys: list[int] = field(default_factory=list)
    applied_keys: list[int] = field(default_factory=list)


class FakeVnc:
    """Accepts many clients, like x11vnc -shared."""

    def __init__(self, *, view_password: str, control_password: str) -> None:
        self.view_password = view_password
        self.control_password = control_password
        self.clients: list[VncClient] = []
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        self._sock.settimeout(0.2)
        self.port = self._sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._accept, daemon=True)

    @property
    def endpoint(self) -> str:
        return f"127.0.0.1:{self.port}"

    @property
    def connection_count(self) -> int:
        return len(self.clients)

    def start(self) -> FakeVnc:
        self._thread.start()
        return self

    def close(self) -> None:
        self._stop.set()
        self._sock.close()
        self._thread.join(timeout=2)

    def __enter__(self) -> FakeVnc:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _accept(self) -> None:
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except TimeoutError, OSError:
                continue
            client = VncClient()
            self.clients.append(client)
            threading.Thread(
                target=self._serve, args=(conn, client), daemon=True
            ).start()

    def _serve(self, conn: socket.socket, client: VncClient) -> None:
        try:
            conn.settimeout(2)
            conn.sendall(RFB_VERSION)
            _recvall(conn, 12)
            conn.sendall(bytes([1, SECURITY_VNC]))
            _recvall(conn, 1)
            challenge = secrets.token_bytes(16)
            conn.sendall(challenge)
            response = _recvall(conn, 16)
            if response == vnc_response(self.control_password, challenge):
                client.password_used = self.control_password
            elif response == vnc_response(self.view_password, challenge):
                client.password_used = self.view_password
            else:
                conn.sendall(b"\x00\x00\x00\x01")
                return
            conn.sendall(b"\x00\x00\x00\x00")
            _recvall(conn, 1)
            conn.sendall(_SERVER_INIT + _FRAMEBUFFER_UPDATE)
            conn.settimeout(0.5)
            while not self._stop.is_set():
                try:
                    message = conn.recv(1024)
                except TimeoutError:
                    continue
                if not message:
                    return
                if message[0] == 4 and len(message) >= 8:
                    key = int.from_bytes(message[4:8], "big")
                    client.seen_keys.append(key)
                    if client.password_used == self.control_password:
                        client.applied_keys.append(key)
        except OSError:
            return
        finally:
            conn.close()


def _recvall(conn: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise OSError("closed")
        buf.extend(chunk)
    return bytes(buf)
