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


def test_password_value_never_crosses_the_extension_boundary(
    connected_browser: BrowserContext,
    fixture_site: str,
    recording_sink: RecordingSink,
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{fixture_site}/recording.html")
    surface = start_recording(connected_browser, fixture_site, page)

    literal = "do-not-record-this"
    page.fill('[data-testid="password"]', literal)
    page.press('[data-testid="password"]', "Tab")
    steps = recording_sink.wait_for_steps(1)
    stored = worker_of(connected_browser).evaluate(
        "() => chrome.storage.local.get('active-recording')"
    )

    assert steps[0]["type"] == "type"
    assert steps[0]["payload"]["value"] == ""
    assert steps[0]["needsSecret"] is True
    assert literal not in str(recording_sink.checkpoints)
    assert literal not in str(stored)

    surface.close()
    page.close()


def test_option_selection_emits_a_select_step(
    connected_browser: BrowserContext,
    fixture_site: str,
    recording_sink: RecordingSink,
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{fixture_site}/recording.html")
    surface = start_recording(connected_browser, fixture_site, page)

    page.select_option('[data-testid="country"]', "nl")
    steps = recording_sink.wait_for_steps(1)

    assert steps[0]["type"] == "select"
    assert steps[0]["label"] == "Select Country"
    assert steps[0]["payload"]["value"] == "nl"
    assert steps[0]["payload"]["target"]["candidates"][0] == {
        "kind": "testid",
        "value": "country",
    }

    surface.close()
    page.close()


def test_extract_toggle_makes_the_next_click_side_effect_free(
    connected_browser: BrowserContext,
    fixture_site: str,
    recording_sink: RecordingSink,
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{fixture_site}/recording.html")
    surface = start_recording(connected_browser, fixture_site, page)

    armed = surface.evaluate(
        """() => chrome.runtime.sendMessage({
          type: "arm-extract",
          mode: "scalar",
          outputName: "save_text",
        })"""
    )
    assert armed == {"armed": True}
    page.click('[data-testid="save"]')
    steps = recording_sink.wait_for_steps(1)

    assert page.locator("body").get_attribute("data-last-click") is None
    assert steps[0]["type"] == "extract"
    assert steps[0]["label"] == "Extract Save"
    assert steps[0]["payload"] == {
        "target": {"candidates": steps[0]["payload"]["target"]["candidates"]},
        "outputName": "save_text",
        "mode": "scalar",
    }

    surface.close()
    page.close()


def test_list_extract_carries_flat_field_bindings(
    connected_browser: BrowserContext,
    fixture_site: str,
    recording_sink: RecordingSink,
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{fixture_site}/recording.html")
    surface = start_recording(connected_browser, fixture_site, page)
    fields = [
        {"name": "name", "subSelector": ".name"},
        {"name": "price", "subSelector": ".price", "attribute": "data-value"},
    ]

    armed = surface.evaluate(
        """(fields) => chrome.runtime.sendMessage({
          type: "arm-extract",
          mode: "list",
          outputName: "rows",
          fields,
        })""",
        fields,
    )
    assert armed == {"armed": True}
    page.click('[data-testid="save"]')
    steps = recording_sink.wait_for_steps(1)

    assert steps[0]["payload"]["mode"] == "list"
    assert steps[0]["payload"]["fields"] == fields

    surface.close()
    page.close()


def test_closed_shadow_target_is_recorded_with_an_immediate_warning(
    connected_browser: BrowserContext,
    fixture_site: str,
    recording_sink: RecordingSink,
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{fixture_site}/recording.html")
    surface = start_recording(connected_browser, fixture_site, page)

    page.locator("#sealed-control").click()
    steps = recording_sink.wait_for_steps(1)
    warning = page.locator('[data-step-by-step-warning="unsupported"]')

    assert warning.is_visible()
    assert warning.text_content() == (
        "This part of the page is sealed off, so the workflow may not be able "
        "to use it later. The step was recorded anyway."
    )
    assert steps[0]["payload"]["target"]["unsupported"] == {
        "reason": "closed-shadow-root",
        "warning": warning.text_content(),
    }

    surface.close()
    page.close()


def test_unreachable_frame_target_is_recorded_with_a_warning(
    connected_browser: BrowserContext,
    fixture_site: str,
    recording_sink: RecordingSink,
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{fixture_site}/recording.html")
    surface = start_recording(connected_browser, fixture_site, page)
    frame = page.frame_locator("#unreachable-frame")

    frame.locator('[data-testid="after-navigation"]').click()
    steps = recording_sink.wait_for_steps(1)

    assert steps[0]["payload"]["target"]["unsupported"]["reason"] == (
        "cross-origin-frame"
    )
    assert (
        "can't reach this embedded part"
        in steps[0]["payload"]["target"]["unsupported"]["warning"]
    )
    assert page.locator('[data-step-by-step-warning="unsupported"]').is_visible()

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
