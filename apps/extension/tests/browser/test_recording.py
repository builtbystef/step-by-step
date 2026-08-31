from typing import Any

import pytest
from conftest import RecordingSink, worker_of
from playwright.sync_api import BrowserContext, Page

pytestmark = pytest.mark.browser


def start_recording(browser: BrowserContext, fixture_site: str, page: Page) -> Page:
    worker = worker_of(browser)
    worker.evaluate(
        """(origin) => chrome.storage.local.set({connection: {origin}})
          .then(() => chrome.storage.local.remove('active-recording'))""",
        fixture_site,
    )
    app = browser.new_page()
    app.goto(f"{fixture_site}/bridge.html")
    app.wait_for_timeout(100)
    app.evaluate(
        """(origin) => window.postMessage({
          channel: "step-by-step",
          type: "recording-pending",
          sessionId: "fixture-session",
          token: "fixture-token",
          backendOrigin: origin,
          workflowId: "fixture-workflow",
          workflowName: "Fixture Workflow",
          mode: "record",
          variables: [],
          secrets: [{id: "fixture-existing", name: "Existing password"}],
        }, origin)""",
        fixture_site,
    )
    app.wait_for_timeout(100)
    app.close()
    surface = browser.new_page()
    surface.goto(f"chrome-extension://{worker.url.split('/')[2]}/popup.html")
    answer = surface.evaluate(
        """async (targetUrl) => {
          const [tab] = await chrome.tabs.query({url: targetUrl});
          await chrome.runtime.sendMessage({
            type: "about-to-start-recording",
            targetTabId: tab.id,
            targetUrl,
          });
          return chrome.runtime.sendMessage({type: "finish-recording-start"});
        }""",
        page.url,
    )
    assert answer == {"started": True}
    return surface


def test_connected_app_hands_a_pending_recording_to_restartable_storage(
    connected_browser: BrowserContext, fixture_site: str
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{fixture_site}/recording.html")
    worker = worker_of(connected_browser)
    worker.evaluate(
        "(origin) => chrome.storage.local.set({connection: {origin}})", fixture_site
    )
    page.reload()
    page.wait_for_timeout(250)

    page.evaluate(
        """(origin) => window.postMessage({
          channel: "step-by-step",
          type: "recording-pending",
          sessionId: "pending-session",
          token: "pending-token",
          backendOrigin: origin,
          workflowId: "workflow-1",
          workflowName: "Invoices",
          mode: "record",
          variables: [{name: "password", secret: true}],
          secrets: [{id: "secret-1", name: "Portal password"}],
        }, origin)""",
        fixture_site,
    )
    page.wait_for_timeout(250)
    stored = worker.evaluate("() => chrome.storage.local.get('active-recording')")[
        "active-recording"
    ]

    assert stored["state"] == "pending"
    assert stored["sessionId"] == "pending-session"
    assert stored["workflowName"] == "Invoices"
    assert stored["secrets"] == [{"id": "secret-1", "name": "Portal password"}]
    assert stored["steps"] == []
    page.close()


def test_insecure_http_page_captures_steps_without_secure_context_apis(
    connected_browser: BrowserContext,
    fixture_site: str,
    insecure_site: str,
    recording_sink: RecordingSink,
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{insecure_site}/recording.html")
    assert page.evaluate("() => typeof crypto.randomUUID") == "undefined"
    surface = start_recording(connected_browser, fixture_site, page)

    page.click('[data-testid="save"]')
    steps = recording_sink.wait_for_steps_after_start(1)

    assert steps[0]["label"] == "Click Save"
    surface.close()
    page.close()


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
    steps = recording_sink.wait_for_steps_after_start(4)

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


def test_finished_recording_binds_password_and_finalizes_directly(
    connected_browser: BrowserContext,
    fixture_site: str,
    recording_sink: RecordingSink,
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{fixture_site}/recording.html")
    surface = start_recording(connected_browser, fixture_site, page)

    page.click('[data-testid="save"]')
    page.fill('[data-testid="password"]', "not-in-the-document")
    page.press('[data-testid="password"]', "Tab")
    recording_sink.wait_for_steps_after_start(2)
    surface.evaluate("() => chrome.runtime.sendMessage({type: 'stop-recording'})")
    surface.locator("input[data-variable-name]").fill("site_password")
    surface.locator("select[data-secret-choice]").select_option("new")
    surface.locator("input[data-secret-name]").fill("Fixture password")
    surface.locator("input[data-secret-value]").fill("one-request-only")
    surface.locator("#save-button").click()
    saved = recording_sink.wait_for_finalization()

    assert recording_sink.auth_captures == []
    assert recording_sink.secret_creations == [
        {"name": "Fixture password", "value": "one-request-only"}
    ]
    assert [step["type"] for step in saved["steps"]] == ["navigate", "click", "type"]
    assert saved["steps"][2]["payload"]["value"] == "{{site_password}}"
    assert "needsSecret" not in saved["steps"][2]
    assert saved["variables"] == [
        {
            "name": "site_password",
            "secret": True,
            "secretId": "created-secret",
            "secretName": "Fixture password",
        }
    ]
    assert "not-in-the-document" not in str(saved)
    assert "one-request-only" not in str(recording_sink.checkpoints)
    assert "one-request-only" not in str(saved)

    surface.close()
    page.close()


def test_taken_recording_secret_name_can_switch_to_an_existing_secret(
    connected_browser: BrowserContext,
    fixture_site: str,
    recording_sink: RecordingSink,
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{fixture_site}/recording.html")
    surface = start_recording(connected_browser, fixture_site, page)

    page.fill('[data-testid="password"]', "never-captured")
    page.press('[data-testid="password"]', "Tab")
    step = recording_sink.wait_for_steps_after_start(1)[0]
    surface.evaluate("() => chrome.runtime.sendMessage({type: 'stop-recording'})")
    conflict = surface.evaluate(
        """(stepId) => chrome.runtime.sendMessage({
          type: "finalize-recording",
          bindings: [{
            stepId,
            name: "password",
            create: {name: "Taken", value: "conflicting-value"},
          }],
        })""",
        step["id"],
    )

    assert conflict == {
        "saved": False,
        "reason": "name-taken",
        "message": (
            "That Secret name is already used. Rename it or pick the existing Secret."
        ),
    }
    assert recording_sink.finalizations == []

    switched = surface.evaluate(
        """(stepId) => chrome.runtime.sendMessage({
          type: "finalize-recording",
          bindings: [{
            stepId,
            name: "password",
            secret: {id: "fixture-existing", name: "Existing password"},
          }],
        })""",
        step["id"],
    )
    saved = recording_sink.wait_for_finalization()

    assert switched == {"saved": True}
    assert recording_sink.secret_creations == [
        {"name": "Taken", "value": "conflicting-value"}
    ]
    assert saved["variables"] == [
        {
            "name": "password",
            "secret": True,
            "secretId": "fixture-existing",
            "secretName": "Existing password",
        }
    ]
    assert "conflicting-value" not in str(saved)

    surface.close()
    page.close()


def test_checked_domain_captures_http_only_cookie_and_both_web_storages(
    connected_browser: BrowserContext,
    fixture_site: str,
    recording_sink: RecordingSink,
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{fixture_site}/recording.html")
    page.evaluate(
        """() => {
          localStorage.setItem('local-token', 'local-secret');
          sessionStorage.setItem('session-token', 'session-secret');
        }"""
    )
    surface = start_recording(connected_browser, fixture_site, page)
    cookie = surface.evaluate(
        """(url) => chrome.cookies.set({
          url,
          name: 'http-only-session',
          value: 'cookie-secret',
          httpOnly: true,
          secure: false,
          sameSite: 'lax',
        })""",
        fixture_site,
    )
    assert cookie["httpOnly"] is True
    assert surface.evaluate("(url) => chrome.cookies.getAll({url})", f"{fixture_site}/")
    surface.evaluate("() => chrome.runtime.sendMessage({type: 'stop-recording'})")
    recording = surface.evaluate(
        "() => chrome.runtime.sendMessage({type: 'recording-state'})"
    )["recording"]
    assert recording["authChoices"] == [
        {
            "domain": "127.0.0.1",
            "checked": False,
            "scope": "organization",
            "organizationSavedAt": None,
            "personalSavedAt": None,
        }
    ]

    answer = surface.evaluate(
        """() => chrome.runtime.sendMessage({
          type: 'finalize-recording',
          bindings: [],
          authSelections: [{domain: '127.0.0.1', checked: true, scope: 'personal'}],
        })"""
    )
    capture = recording_sink.wait_for_auth_capture()["captures"][0]

    assert answer == {"saved": True}
    assert capture["scope"] == "personal"
    cookie = next(
        item for item in capture["cookies"] if item["name"] == "http-only-session"
    )
    assert cookie["httpOnly"] is True
    assert capture["origins"] == [
        {
            "origin": fixture_site,
            "local_storage": [{"name": "local-token", "value": "local-secret"}],
        }
    ]
    assert capture["session_storage"] == [
        {
            "origin": fixture_site,
            "items": [{"name": "session-token", "value": "session-secret"}],
        }
    ]

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
    steps = recording_sink.wait_for_steps_after_start(1)
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
    steps = recording_sink.wait_for_steps_after_start(1)

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
    steps = recording_sink.wait_for_steps_after_start(1)

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
    steps = recording_sink.wait_for_steps_after_start(1)

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
    steps = recording_sink.wait_for_steps_after_start(1)
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
    steps = recording_sink.wait_for_steps_after_start(1)

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


def test_recording_opens_with_a_navigate_step_to_the_page_it_started_on(
    connected_browser: BrowserContext,
    fixture_site: str,
    recording_sink: RecordingSink,
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{fixture_site}/recording.html")
    surface = start_recording(connected_browser, fixture_site, page)

    page.click('[data-testid="save"]')
    steps = recording_sink.wait_for_steps(2)

    assert steps[0] == {
        "id": steps[0]["id"],
        "type": "navigate",
        "label": "Navigate to 127.0.0.1",
        "optional": False,
        "disabled": False,
        "screenshot": False,
        "payload": {"url": f"{fixture_site}/recording.html"},
    }
    assert steps[1]["label"] == "Click Save"

    surface.close()
    page.close()


def test_aria_label_names_a_target_whose_own_text_is_unusable(
    connected_browser: BrowserContext,
    fixture_site: str,
    recording_sink: RecordingSink,
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{fixture_site}/recording.html")
    surface = start_recording(connected_browser, fixture_site, page)

    page.click("#overlay-control")
    steps = recording_sink.wait_for_steps_after_start(1)
    candidates = steps[0]["payload"]["target"]["candidates"]

    assert "text" not in {candidate["kind"] for candidate in candidates}
    assert {"kind": "label", "value": "Play the video"} in candidates
    assert page.locator('[data-step-by-step-warning="unsupported"]').count() == 0

    surface.close()
    page.close()


def test_position_only_target_warns_while_the_recording_is_open(
    connected_browser: BrowserContext,
    fixture_site: str,
    recording_sink: RecordingSink,
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{fixture_site}/recording.html")
    surface = start_recording(connected_browser, fixture_site, page)

    page.click("#positional-control")
    steps = recording_sink.wait_for_steps_after_start(1)
    warning = page.locator('[data-step-by-step-warning="unsupported"]')

    assert [
        candidate["kind"] for candidate in steps[0]["payload"]["target"]["candidates"]
    ] == ["css"]
    assert warning.text_content() == (
        "Only where this element sits on the page could be recorded. A layout "
        "change will lose it. The step was recorded anyway."
    )

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
    steps = recording_sink.wait_for_steps_after_start(2)

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
    steps = recording_sink.wait_for_steps_after_start(1)

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


def hand_repick(page: Page, fixture_site: str) -> None:
    worker = worker_of(page.context)
    pending = {
        "channel": "step-by-step",
        "type": "recording-pending",
        "sessionId": "repick-session",
        "token": "repick-token",
        "backendOrigin": fixture_site,
        "workflowId": "fixture-workflow",
        "workflowName": "Fixture Workflow",
        "mode": "repick",
        "stepId": "step-9",
    }
    for _ in range(20):
        worker.evaluate(
            """(origin) => chrome.storage.local.set({connection: {origin}})
              .then(() => chrome.storage.local.remove('active-recording'))""",
            fixture_site,
        )
        page.evaluate(
            "([message, origin]) => window.postMessage(message, origin)",
            [pending, fixture_site],
        )
        page.wait_for_timeout(50)
        stored = worker.evaluate("() => chrome.storage.local.get('active-recording')")[
            "active-recording"
        ]
        if (
            stored is not None
            and stored.get("sessionId") == "repick-session"
            and stored.get("mode") == "repick"
            and stored.get("state") == "pending"
        ):
            return
    raise AssertionError("the extension did not keep the Re-pick session")


def start_repick(browser: BrowserContext, fixture_site: str, page: Page) -> Page:
    hand_repick(page, fixture_site)
    worker = worker_of(browser)
    surface = browser.new_page()
    surface.goto(f"chrome-extension://{worker.url.split('/')[2]}/popup.html")
    answer = surface.evaluate(
        """async (targetUrl) => {
          const [tab] = await chrome.tabs.query({url: targetUrl});
          await chrome.runtime.sendMessage({
            type: "about-to-start-recording",
            targetTabId: tab.id,
            targetUrl,
          });
          return chrome.runtime.sendMessage({type: "finish-recording-start"});
        }""",
        page.url,
    )
    assert answer == {"started": True}
    return surface


def test_repick_pending_is_stored_scoped_to_one_step(
    connected_browser: BrowserContext, fixture_site: str
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{fixture_site}/recording.html?repick-pending=1")
    page.wait_for_timeout(250)
    hand_repick(page, fixture_site)
    stored = worker_of(connected_browser).evaluate(
        "() => chrome.storage.local.get('active-recording')"
    )["active-recording"]

    assert stored["state"] == "pending"
    assert stored["mode"] == "repick"
    assert stored["stepId"] == "step-9"
    assert stored["sessionId"] == "repick-session"
    page.close()


def test_repick_click_messages_candidates_and_does_not_finalize(
    connected_browser: BrowserContext,
    fixture_site: str,
    recording_sink: RecordingSink,
) -> None:
    page = connected_browser.new_page()
    page.goto(f"{fixture_site}/recording.html?repick=1")
    page.evaluate(
        """() => {
          window.__repick = null;
          window.addEventListener("message", (event) => {
            if (event.data && event.data.type === "repick-candidates") {
              window.__repick = event.data;
            }
          });
        }"""
    )
    surface = start_repick(connected_browser, fixture_site, page)

    page.click('[data-testid="save"]')
    page.wait_for_function("() => window.__repick !== null")
    message = page.evaluate("() => window.__repick")

    assert message["sessionId"] == "repick-session"
    assert message["stepId"] == "step-9"
    assert message["candidates"][0] == {"kind": "testid", "value": "save"}
    assert {"kind": "role", "value": 'button[name="Save"]'} in message["candidates"]
    assert recording_sink.finalizations == []
    assert recording_sink.checkpoints == []

    stored = worker_of(connected_browser).evaluate(
        "() => chrome.storage.local.get('active-recording')"
    )
    assert stored.get("active-recording") in (None, {})

    surface.close()
    page.close()
