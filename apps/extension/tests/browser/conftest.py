"""What the extension's browser tier shares: a real Chromium with the package
loaded unpacked, and a real origin to be a fake instance at.

This is the harness the recorder slices build on. It proves what a headless
browser can prove: that the package Chrome is handed loads, and that the
handshake is refused unless it is the one this connect attempt asked for. The
permission grant itself is a native Chrome dialog raised from a click in the
popup, which no automation can drive — that check is attended, in a real
browser, and the issue names it.
"""

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
"""The unpacked extension: the directory Chrome loads and the zip carries."""

PAGES = Path(__file__).parent / "pages"

EXTENSION_PREFIX = "/ext/"
"""Where the fixture site serves the package's own modules from.

A page importing them is how a module Chrome would run inside the extension is
exercised from outside it — the file under test is the file that ships.
"""


@pytest.fixture(scope="session")
def fixture_site() -> Iterator[str]:
    """The origin that stands in for an instance."""
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
def other_site(fixture_site: str) -> str:
    """A second origin on the same server: `localhost` is not `127.0.0.1`."""
    return fixture_site.replace("127.0.0.1", "localhost")


LIVE_CODE = "ABCD-EFGH-JKLM"
"""The one connect code the fixture instance will accept."""


class RecordingSink:
    """The fixture instance's observable recording boundary."""

    def __init__(self) -> None:
        self.condition = threading.Condition()
        self.checkpoints: list[dict[str, Any]] = []

    def clear(self) -> None:
        with self.condition:
            self.checkpoints.clear()

    def append(self, checkpoint: dict[str, Any]) -> None:
        with self.condition:
            self.checkpoints.append(deepcopy(checkpoint))
            self.condition.notify_all()

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
    """The fixture pages, with the extension's own modules beside them.

    It answers as much of an instance as the extension can tell apart: the
    connect page at the address the extension opens, and the one endpoint a
    connect code is spent at.
    """

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
            "/checkpoint"
        ):
            RECORDING_SINK.append(asked)
            body = b"{}"
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
    """The directory Chrome loads, for a test that reads the manifest."""
    return PACKAGE


@pytest.fixture(scope="session")
def playwright_driver() -> Iterator[Playwright]:
    with sync_playwright() as driver:
        yield driver


@pytest.fixture(scope="session")
def extension(
    playwright_driver: Playwright, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[BrowserContext]:
    """One browser with the unpacked package loaded, for the whole tier.

    A persistent context, because an extension has nowhere to live in an
    incognito one — which is also the shape a person's own Chrome has.
    """
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
    """The id Chrome gave the package, taken from its running service worker."""
    return worker_of(extension).url.split("/")[2]


@pytest.fixture(scope="session")
def connected_browser(
    playwright_driver: Playwright,
    tmp_path_factory: pytest.TempPathFactory,
    fixture_site: str,
) -> Iterator[BrowserContext]:
    """A browser holding the package with the fixture instance already granted.

    The one thing this fakes is the one thing no automation can do: Chrome
    raises the optional-permission dialog from a click in the popup, and there
    is nothing to click it with. So the origin is written into a copy of the
    manifest as a host permission, which is the state the dialog would leave
    the browser in — and everything after the dialog is then the real thing:
    the popup's own click path, the tab the worker opens, the bridge it
    injects, the nonce it judges, and what it stores.

    `test_the_unpacked_package_loads_under_its_pinned_id` is the counterweight:
    it loads the package as it ships, unedited.
    """
    granted = tmp_path_factory.mktemp("granted-package")
    shutil.copytree(PACKAGE, granted, dirs_exist_ok=True)
    manifest = json.loads((granted / "manifest.json").read_text())
    manifest["host_permissions"] = [f"{fixture_site}/*"]
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
    """The extension's service worker, started if it has not been yet."""
    workers = context.service_workers
    if not workers:
        workers = [context.wait_for_event("serviceworker", timeout=10_000)]
    return workers[0]
