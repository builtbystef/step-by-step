"""Recorder behavior through the unpacked extension's emitted checkpoints."""

from typing import Any

import pytest
from conftest import RecordingSink, worker_of
from playwright.sync_api import BrowserContext, Page

pytestmark = pytest.mark.browser


def start_recording(browser: BrowserContext, fixture_site: str, page: Page) -> Page:
    """Start through the extension's own command surface, as its popup does."""
    worker = worker_of(browser)
    worker.evaluate(
        "(origin) => chrome.storage.local.set({connection: {origin}})", fixture_site
    )
    surface = browser.new_page()
    surface.goto(f"chrome-extension://{worker.url.split('/')[2]}/popup.html")
    answer = surface.evaluate(
        """([targetUrl, origin]) => chrome.runtime.sendMessage({
          type: "start-recording",
          targetUrl,
          sessionId: "fixture-session",
          token: "fixture-token",
          backendOrigin: origin,
        })""",
        [page.url, fixture_site],
    )
    assert answer == {"started": True}
    return surface


def assert_safe_message(value: Any) -> None:
    if isinstance(value, dict):
        forbidden = {"responseBody", "requestBody", "headers", "network"}
        assert forbidden.isdisjoint(value)
        for nested in value.values():
            assert_safe_message(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_safe_message(nested)


def test_clicks_emit_ranked_verified_steps_in_order_and_checkpoint_them(
    connected_browser: BrowserContext,
    fixture_site: str,
    recording_sink: RecordingSink,
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{fixture_site}/recording.html")
    surface = start_recording(connected_browser, fixture_site, page)

    page.click('[data-testid="save"]')
    page.evaluate(
        """() => {
          document.querySelector('[data-testid="second"]').click();
          document.querySelector('[title="Repeated title"]').click();
        }"""
    )
    page.fill('[data-testid="email"]', "person@example.test")
    page.press('[data-testid="email"]', "Tab")
    steps = recording_sink.wait_for_steps(4)

    assert [step["label"] for step in steps] == [
        "Click Save",
        "Click Second",
        "Click One repeated title",
        "Type into Email",
    ]
    assert [step["payload"]["target"]["candidates"][0] for step in steps[:2]] == [
        {"kind": "testid", "value": "save"},
        {"kind": "testid", "value": "second"},
    ]
    assert {"kind": "role", "value": 'button[name="Save"]'} in steps[0]["payload"][
        "target"
    ]["candidates"]
    assert [
        candidate["kind"] for candidate in steps[0]["payload"]["target"]["candidates"]
    ] == ["testid", "role", "text", "css"]
    assert "title" not in {
        candidate["kind"] for candidate in steps[2]["payload"]["target"]["candidates"]
    }
    assert steps[3]["type"] == "type"
    assert steps[3]["payload"]["value"] == "person@example.test"
    assert steps[0]["optional"] is False
    assert steps[0]["disabled"] is False
    assert steps[0]["screenshot"] is False
    assert "verified" not in str(steps)
    assert_safe_message(recording_sink.checkpoints)

    surface.close()
    page.close()


def test_navigation_is_correlated_without_mixing_page_loads(
    connected_browser: BrowserContext,
    fixture_site: str,
    recording_sink: RecordingSink,
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{fixture_site}/recording.html")
    surface = start_recording(connected_browser, fixture_site, page)

    page.click('[data-testid="next"]')
    page.wait_for_url(f"{fixture_site}/destination.html")
    page.click('[data-testid="after-navigation"]')
    steps = recording_sink.wait_for_steps(2)

    assert [step["type"] for step in steps] == ["click", "click"]
    assert steps[0]["payload"]["assertedNavigation"] is True
    assert steps[0]["payload"]["target"]["candidates"][0]["value"] == "next"
    assert steps[1]["payload"]["target"]["candidates"][0]["value"] == (
        "after-navigation"
    )

    surface.close()
    page.close()


def test_browser_navigation_emits_a_standalone_navigate_step(
    connected_browser: BrowserContext,
    fixture_site: str,
    recording_sink: RecordingSink,
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{fixture_site}/recording.html")
    surface = start_recording(connected_browser, fixture_site, page)

    page.goto(f"{fixture_site}/destination.html")
    steps = recording_sink.wait_for_steps(1)

    assert steps == [
        {
            "id": steps[0]["id"],
            "type": "navigate",
            "label": "Navigate to 127.0.0.1",
            "optional": False,
            "disabled": False,
            "screenshot": False,
            "payload": {"url": f"{fixture_site}/destination.html"},
        }
    ]

    surface.close()
    page.close()
