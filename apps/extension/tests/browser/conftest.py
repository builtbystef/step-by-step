import http.server
import json
import shutil
import threading
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
from playwright.sync_api import BrowserContext, Playwright, Worker, sync_playwright

PACKAGE = Path(__file__).parents[2] / "src"

PAGES = Path(__file__).parent / "pages"

EXTENSION_PREFIX = "/ext/"


@pytest.fixture(scope="session")
def fixture_site() -> Iterator[str]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), SiteHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture(scope="session")
def insecure_site(fixture_site: str) -> str:
    return fixture_site.replace("127.0.0.1", "0.0.0.0")


@pytest.fixture(scope="session")
def other_site(fixture_site: str) -> str:
    return fixture_site.replace("127.0.0.1", "localhost")


LIVE_CODE = "ABCD-EFGH-JKLM"


class RecordingSink:
    def __init__(self) -> None:
        self.condition = threading.Condition()
        self.checkpoints: list[dict[str, Any]] = []
        self.finalizations: list[dict[str, Any]] = []
        self.secret_creations: list[dict[str, Any]] = []
        self.auth_captures: list[dict[str, Any]] = []

    def clear(self) -> None:
        with self.condition:
            self.checkpoints.clear()
            self.finalizations.clear()
            self.secret_creations.clear()
            self.auth_captures.clear()

    def append(self, checkpoint: dict[str, Any]) -> None:
        with self.condition:
            self.checkpoints.append(deepcopy(checkpoint))
            self.condition.notify_all()

    def finalize(self, document: dict[str, Any]) -> None:
        with self.condition:
            self.finalizations.append(deepcopy(document))
            self.condition.notify_all()

    def wait_for_finalization(self) -> dict[str, Any]:
        with self.condition:
            ready = self.condition.wait_for(
                lambda: bool(self.finalizations), timeout=10
            )
            assert ready
            return deepcopy(self.finalizations[-1])

    def create_secret(self, body: dict[str, Any]) -> dict[str, Any]:
        with self.condition:
            self.secret_creations.append(deepcopy(body))
            self.condition.notify_all()
        return {"id": "created-secret", "name": body.get("name")}

    def capture_auth(self, body: dict[str, Any]) -> None:
        with self.condition:
            self.auth_captures.append(deepcopy(body))
            self.condition.notify_all()

    def wait_for_auth_capture(self) -> dict[str, Any]:
        with self.condition:
            ready = self.condition.wait_for(
                lambda: bool(self.auth_captures), timeout=10
            )
            assert ready
            return deepcopy(self.auth_captures[-1])

    def wait_for_steps_after_start(self, count: int) -> list[dict[str, Any]]:
        """The Steps past the navigate Step that opens every recording."""
        steps = self.wait_for_steps(count + 1)
        assert steps[0]["type"] == "navigate"
        return steps[1:]

    def wait_for_steps(self, count: int) -> list[dict[str, Any]]:
        with self.condition:
            ready = self.condition.wait_for(
                lambda: (
                    bool(self.checkpoints)
                    and len(self.checkpoints[-1].get("steps", [])) >= count
                ),
                timeout=10,
            )
            assert ready, self.checkpoints
            return deepcopy(cast(list[dict[str, Any]], self.checkpoints[-1]["steps"]))


RECORDING_SINK = RecordingSink()


@pytest.fixture
def recording_sink() -> RecordingSink:
    RECORDING_SINK.clear()
    return RECORDING_SINK


class SiteHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(PAGES), **kwargs)  # ty: ignore

    def translate_path(self, path: str) -> str:
        if path.startswith(EXTENSION_PREFIX):
            inside = path[len(EXTENSION_PREFIX) :].split("?")[0].split("#")[0]
            return str(PACKAGE.joinpath(*inside.split("/")))
        if path.split("?")[0] == "/connect":
            return str(PAGES / "connect-page.html")
        return super().translate_path(path)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        try:
            asked = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            asked = {}
        if self.path.startswith("/api/recording-sessions/") and self.path.endswith(
            "/auth-state-options"
        ):
            body = json.dumps(
                [
                    {
                        "domain": "127.0.0.1",
                        "organization_saved_at": None,
                        "personal_saved_at": None,
                    }
                ]
            ).encode()
            status = 200
        elif self.path.startswith("/api/recording-sessions/") and self.path.endswith(
            "/secrets"
        ):
            identity = RECORDING_SINK.create_secret(asked)
            if asked.get("name") == "Taken":
                refusal = {
                    "code": "name_taken",
                    "message": "that Secret name is already used",
                }
                body = json.dumps(refusal).encode()
                status = 409
            else:
                body = json.dumps(identity).encode()
                status = 201
        elif self.path.startswith("/api/recording-sessions/") and self.path.endswith(
            "/auth-states"
        ):
            RECORDING_SINK.capture_auth(asked)
            body = b"{}"
            status = 200
        elif self.path.startswith("/api/recording-sessions/") and self.path.endswith(
            "/checkpoint"
        ):
            RECORDING_SINK.append(asked)
            body = b"{}"
            status = 200
        elif self.path.startswith("/api/recording-sessions/") and self.path.endswith(
            "/finalize"
        ):
            RECORDING_SINK.finalize(asked)
            body = json.dumps(asked).encode()
            status = 200
        elif self.path == "/api/extension/connect":
            spent = asked.get("code") == LIVE_CODE
            body = b"{}" if spent else b'{"code":"bad_code","message":"no"}'
            status = 200 if spent else 401
        else:
            self.send_error(404)
            return
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture(scope="session")
def package() -> Path:
    return PACKAGE


@pytest.fixture(scope="session")
def playwright_driver() -> Iterator[Playwright]:
    with sync_playwright() as driver:
        yield driver


@pytest.fixture(scope="session")
def extension(
    playwright_driver: Playwright, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[BrowserContext]:
    context = playwright_driver.chromium.launch_persistent_context(
        user_data_dir=str(tmp_path_factory.mktemp("chrome-profile")),
        headless=True,
        channel="chromium",
        args=[
            f"--disable-extensions-except={PACKAGE}",
            f"--load-extension={PACKAGE}",
        ],
    )
    try:
        yield context
    finally:
        context.close()


@pytest.fixture(scope="session")
def extension_id(extension: BrowserContext) -> str:
    return worker_of(extension).url.split("/")[2]


@pytest.fixture(scope="session")
def connected_browser(
    playwright_driver: Playwright,
    tmp_path_factory: pytest.TempPathFactory,
    fixture_site: str,
    insecure_site: str,
) -> Iterator[BrowserContext]:
    granted = tmp_path_factory.mktemp("granted-package")
    shutil.copytree(PACKAGE, granted, dirs_exist_ok=True)
    manifest = json.loads((granted / "manifest.json").read_text())
    manifest["host_permissions"] = [
        f"{fixture_site.rsplit(':', 1)[0]}/*",
        f"{insecure_site.rsplit(':', 1)[0]}/*",
    ]
    (granted / "manifest.json").write_text(json.dumps(manifest, indent=2))

    context = playwright_driver.chromium.launch_persistent_context(
        user_data_dir=str(tmp_path_factory.mktemp("granted-profile")),
        headless=True,
        channel="chromium",
        args=[
            f"--disable-extensions-except={granted}",
            f"--load-extension={granted}",
        ],
    )
    try:
        yield context
    finally:
        context.close()


def worker_of(context: BrowserContext) -> Worker:
    workers = context.service_workers
    if not workers:
        workers = [context.wait_for_event("serviceworker", timeout=10_000)]
    return workers[0]
