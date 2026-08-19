"""The connect handshake, in a browser that really loaded the package.

Two rules are on trial. A message reaches the service worker only if the
bridge in the page believed where it came from, and the worker acts on it only
if it is the attempt the worker itself opened. Each is exercised where it runs:
the bridge inside a page, the judgement inside the extension's own origin.
"""

import json
from base64 import b64decode
from hashlib import sha256
from pathlib import Path

import pytest
from conftest import LIVE_CODE, worker_of
from playwright.sync_api import BrowserContext, Page, Worker

pytestmark = pytest.mark.browser

NONCE = "f2b1" * 16
"""A nonce shaped like the ones the worker mints, for tests that supply one."""


def test_the_unpacked_package_loads_under_its_pinned_id(
    extension: BrowserContext, extension_id: str, package: Path
) -> None:
    """Chrome accepted the directory, started the worker, and gave the package
    the id the manifest's key pins — not one derived from where it was
    installed from."""
    manifest = json.loads((package / "manifest.json").read_text())

    assert extension_id == id_from_key(b64decode(manifest["key"]))
    assert extension.service_workers[0].url.endswith("/service-worker.js")


def id_from_key(key: bytes) -> str:
    """The extension id a pinned key produces, by Chrome's own derivation."""
    digest = sha256(key).hexdigest()[:32]
    return "".join("abcdefghijklmnop"[int(digit, 16)] for digit in digest)


def test_a_handshake_from_the_page_itself_is_forwarded(
    extension: BrowserContext, fixture_site: str
) -> None:
    page = extension.new_page()
    page.goto(f"{fixture_site}/bridge.html")
    page.wait_for_function("window.bridgeInstalled === true")

    page.evaluate(
        """(nonce) => window.postMessage(
            { channel: "step-by-step", type: "connect-handshake",
              nonce, instanceOrigin: window.location.origin },
            window.location.origin,
        )""",
        NONCE,
    )

    page.wait_for_function("window.forwarded.length === 1")
    assert page.evaluate("window.forwarded[0].nonce") == NONCE
    # And the page is told, which is what the connect screen waits for.
    page.wait_for_function("window.accepted.length === 1")
    page.close()


def test_a_handshake_from_another_origin_is_never_forwarded(
    extension: BrowserContext, fixture_site: str, other_site: str
) -> None:
    """A frame from somewhere else, saying everything the connect page says."""
    page = extension.new_page()
    page.goto(f"{fixture_site}/bridge.html")
    page.wait_for_function("window.bridgeInstalled === true")

    page.evaluate(
        """([source, origin, nonce]) => {
            const claimed = encodeURIComponent(origin);
            const frame = document.querySelector("#other");
            frame.src = `${source}/intruder.html?nonce=${nonce}&origin=${claimed}`;
            return new Promise((loaded) => { frame.onload = loaded; });
        }""",
        [other_site, fixture_site, NONCE],
    )
    # The frame posts as it loads; give the message every chance to arrive.
    page.wait_for_timeout(250)

    assert page.evaluate("window.forwarded") == []
    page.close()


def test_the_worker_refuses_a_handshake_the_attempt_did_not_ask_for(
    extension: BrowserContext, extension_id: str
) -> None:
    """The judgement itself, run inside the extension's own origin.

    The page's own guard is one gate and this is the other: even a message that
    reached the worker is refused unless the tab, the origin, and the nonce are
    all the attempt's.
    """
    page = extension.new_page()
    page.goto(f"chrome-extension://{extension_id}/popup.html")

    verdicts = page.evaluate(
        """async (nonce) => {
            const { judgeHandshake } = await import("./lib/handshake.js");
            const origin = "https://steps.example.com";
            const attempt = { origin, nonce, tabId: 4 };
            const sender = {
                id: chrome.runtime.id, origin, url: `${origin}/connect`,
                frameId: 0, tab: { id: 4 },
            };
            const handshake = {
                channel: "step-by-step", type: "connect-handshake",
                nonce, instanceOrigin: origin,
            };
            const judge = (message, from) => judgeHandshake({
                message, sender: from ?? sender, attempt,
                extensionId: chrome.runtime.id,
            });
            const elsewhere = { ...sender, origin: "https://elsewhere.example" };
            return {
                asked: judge(handshake),
                wrongNonce: judge({ ...handshake, nonce: "0".repeat(64) }),
                wrongOrigin: judge(handshake, elsewhere),
                anotherTab: judge(handshake, { ...sender, tab: { id: 9 } }),
            };
        }""",
        NONCE,
    )

    assert verdicts["asked"] == {
        "accepted": True,
        "origin": "https://steps.example.com",
    }
    assert verdicts["wrongNonce"] == {"accepted": False, "reason": "wrong-nonce"}
    assert verdicts["wrongOrigin"] == {"accepted": False, "reason": "wrong-origin"}
    assert verdicts["anotherTab"] == {
        "accepted": False,
        "reason": "not-the-connected-tab",
    }
    page.close()


def test_connecting_from_the_popup_ends_with_the_instance_stored(
    connected_browser: BrowserContext, fixture_site: str
) -> None:
    """The whole path after the permission dialog, in one go.

    The popup takes the address, the worker opens the instance's connect page,
    injects the bridge, and judges the nonce that comes back — and what is left
    afterwards is a browser that knows which instance it belongs to.
    """
    worker = worker_of(connected_browser)
    popup = open_popup(connected_browser, worker)

    popup.fill("#address", fixture_site)
    with connected_browser.expect_page() as opened:
        popup.click("#connect-button")
    page = opened.value

    page.wait_for_function("window.connectedVersion !== undefined", timeout=10_000)
    assert page.url.startswith(f"{fixture_site}/connect?nonce=")
    assert "connected" in text_of(page, "#state")

    stored = worker.evaluate("chrome.storage.local.get('connection')")
    assert stored["connection"]["origin"] == fixture_site
    # And the attempt is over: a nonce is good for the one handshake it opened.
    assert worker.evaluate("chrome.storage.session.get('connect-attempt')") == {}

    # The popup was open while it happened, and says so without being reopened.
    popup.wait_for_selector("#connected:not([hidden])")
    assert fixture_site in text_of(popup, "#connected")

    disconnect(popup, page)


def test_a_connect_code_is_the_way_in_when_the_page_never_hands_it_over(
    connected_browser: BrowserContext, fixture_site: str
) -> None:
    """The fallback, from the popup: a wrong code is refused by the instance
    and a live one connects, without the connect page being involved."""
    worker = worker_of(connected_browser)
    popup = open_popup(connected_browser, worker)
    popup.fill("#address", fixture_site)
    popup.click("#code-fallback summary")

    popup.fill("#code", "ZZZZ-ZZZZ-ZZZZ")
    popup.click("#code-button")
    popup.wait_for_function(
        "() => document.querySelector('#note').textContent.length > 0"
    )
    assert "not valid" in text_of(popup, "#note")
    assert worker.evaluate("chrome.storage.local.get('connection')") == {}

    popup.fill("#code", LIVE_CODE)
    popup.click("#code-button")
    popup.wait_for_selector("#connected:not([hidden])")

    stored = worker.evaluate("chrome.storage.local.get('connection')")
    assert stored["connection"]["origin"] == fixture_site

    disconnect(popup)


def text_of(page: Page, selector: str) -> str:
    """What an element says, once something has waited for it to say anything."""
    found = page.text_content(selector)
    assert found is not None, selector
    return found


def open_popup(context: BrowserContext, worker: Worker) -> Page:
    """The popup, in a tab — the same page Chrome renders under the toolbar."""
    popup = context.new_page()
    popup.goto(f"chrome-extension://{worker.url.split('/')[2]}/popup.html")
    popup.wait_for_selector("#connect:not([hidden]), #connected:not([hidden])")
    return popup


def disconnect(popup: Page, *also: Page) -> None:
    """Leave the browser as it was found: these two share one profile."""
    if popup.is_visible("#disconnect"):
        popup.click("#disconnect")
        popup.wait_for_selector("#connect:not([hidden])")
    popup.close()
    for page in also:
        page.close()
