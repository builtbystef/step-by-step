"""What the browser tier's tests share: a real Chromium and a real origin.

The fixture pages are served over HTTP from `pages/` rather than opened as
`file://` URLs, because a Target addresses frames and a frame's document has
to come from somewhere a page can embed. The server binds an ephemeral port on
the loopback, so two runs of this tier never collide.
"""

import threading
from collections.abc import Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, Playwright, sync_playwright

PAGES = Path(__file__).parent / "pages"


@pytest.fixture(scope="session")
def fixture_site() -> Iterator[str]:
    """The origin the fixture pages are served from."""
    handler = partial(QuietHandler, directory=str(PAGES))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class QuietHandler(SimpleHTTPRequestHandler):
    """`SimpleHTTPRequestHandler`, without a line of stderr per request."""

    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture(scope="session")
def playwright_driver() -> Iterator[Playwright]:
    with sync_playwright() as driver:
        yield driver


@pytest.fixture(scope="session")
def browser(playwright_driver: Playwright) -> Iterator[Browser]:
    """One Chromium for the tier.

    Headless: a Run's browser is headed on the Worker's display, but nothing
    this module does can tell the difference, and a display is not this tier's
    to require.
    """
    launched = playwright_driver.chromium.launch()
    try:
        yield launched
    finally:
        launched.close()


@pytest.fixture
def page(browser: Browser) -> Iterator[Page]:
    """A context of its own per test, so no page leaves state for the next."""
    context = browser.new_context()
    try:
        yield context.new_page()
    finally:
        context.close()
