import threading
from collections.abc import Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, Playwright

PAGES = Path(__file__).parent / "pages"


def serve_pages(host: str) -> Iterator[str]:
    handler = partial(QuietHandler, directory=str(PAGES))
    server = ThreadingHTTPServer((host, 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    bound_host, port = server.server_address[:2]
    try:
        yield f"http://{bound_host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.fixture(scope="session")
def fixture_site() -> Iterator[str]:
    yield from serve_pages("127.0.0.1")


@pytest.fixture(scope="session")
def other_site() -> Iterator[str]:
    yield from serve_pages("127.0.0.2")


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


@pytest.fixture(scope="session")
def browser(playwright_driver: Playwright) -> Iterator[Browser]:
    launched = playwright_driver.chromium.launch()
    try:
        yield launched
    finally:
        launched.close()


@pytest.fixture
def page(browser: Browser) -> Iterator[Page]:
    context = browser.new_context()
    try:
        yield context.new_page()
    finally:
        context.close()
