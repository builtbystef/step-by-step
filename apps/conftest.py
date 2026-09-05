from collections.abc import Iterator

import pytest
from playwright.sync_api import Playwright, sync_playwright


@pytest.fixture(scope="session")
def playwright_driver() -> Iterator[Playwright]:
    # Extension and Worker tests run together in CI. Two session-wide sync
    # drivers would try to start nested event loops on the same thread.
    with sync_playwright() as driver:
        yield driver
