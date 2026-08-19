"""Finding a Step's element again, on pages that have moved on.

The seam the spec names for this module: the module itself, driven against
local fixture pages through a real browser. Every example here is one the
spec's Testing Decisions wrote down. Targets are built the way a Run builds
them — from the stored Step document — rather than from the module's own
value objects, because that mapping is the half of the contract the recorder
writes.
"""

from time import monotonic
from typing import Any

import pytest
from playwright.sync_api import Page
from step_by_step_worker.selectors import (
    Deadline,
    Resolved,
    SelectorFailure,
    Target,
    resolve,
)

pytestmark = pytest.mark.browser


def target(*candidates: dict[str, Any], **rest: Any) -> Target:
    """A Target as the Step document holds one."""
    return Target.from_document({"candidates": list(candidates), **rest})


def test_a_dropped_test_id_falls_through_to_the_next_candidate(
    page: Page, fixture_site: str
) -> None:
    """The recorded best way is gone; the next one down finds the element."""
    page.goto(f"{fixture_site}/drifted-save.html")
    drifted = target(
        {"kind": "testid", "value": "save"},
        {"kind": "role", "value": 'button[name="Save"]'},
        {"kind": "css", "value": "#save-button"},
    )

    found = resolve(page, drifted, Deadline.in_ms(2_000))

    assert isinstance(found, Resolved)
    assert found.rank == 1
    assert found.candidate_count == 3
    assert found.locator.get_attribute("id") == "save-button"


def test_a_candidate_matching_two_elements_is_skipped(
    page: Page, fixture_site: str
) -> None:
    """Ambiguity is rejected, even where taking the first would have 'worked'."""
    page.goto(f"{fixture_site}/two-saves.html")
    ambiguous = target(
        {"kind": "role", "value": 'button[name="Save"]'},
        {"kind": "css", "value": "#invoice button"},
    )

    found = resolve(page, ambiguous, Deadline.in_ms(2_000))

    assert isinstance(found, Resolved)
    assert found.rank == 1
    assert found.locator.get_attribute("id") == "save-invoice"


def test_a_target_nothing_matches_fails_at_the_deadline(
    page: Page, fixture_site: str
) -> None:
    """The timeout is the retry budget: giving up early would waste it."""
    page.goto(f"{fixture_site}/two-saves.html")
    hopeless = target(
        {"kind": "testid", "value": "save"},
        {"kind": "role", "value": 'button[name="Save"]'},
    )

    started = monotonic()
    found = resolve(page, hopeless, Deadline.in_ms(1_000))
    took_ms = (monotonic() - started) * 1000

    assert isinstance(found, SelectorFailure)
    assert found.candidate_count == 2
    assert found.walks > 1
    assert took_ms >= 1_000


def test_an_element_that_arrives_late_is_found_by_a_later_walk(
    page: Page, fixture_site: str
) -> None:
    """The list is walked again until the deadline, and each walk is announced."""
    page.goto(f"{fixture_site}/late-button.html")
    late = target({"kind": "role", "value": 'button[name="Save"]'})
    walks: list[int] = []

    started = monotonic()
    found = resolve(page, late, Deadline.in_ms(30_000), on_walk=walks.append)
    took_ms = (monotonic() - started) * 1000

    assert isinstance(found, Resolved)
    assert found.rank == 0
    assert found.walks > 1
    assert walks == list(range(1, found.walks + 1))
    assert 2_000 <= took_ms < 10_000


def test_a_shadow_path_resolves_hop_by_hop(page: Page, fixture_site: str) -> None:
    """Each open shadow root narrows the scope the candidate is read in.

    Every hop carries its weight here: the page, the outer shadow root, and
    the inner one each hold a button named Save, so a path that stopped one
    hop short would find two of them and reject them both.
    """
    page.goto(f"{fixture_site}/shadow-card.html")
    shadowed = target(
        {
            "kind": "role",
            "value": 'button[name="Save"]',
            "shadowPath": ["user-card", "address-panel"],
        }
    )

    found = resolve(page, shadowed, Deadline.in_ms(2_000))

    assert isinstance(found, Resolved)
    assert found.locator.get_attribute("id") == "address-save"


def test_a_frame_path_resolves_inside_the_frame_it_addresses(
    page: Page, fixture_site: str
) -> None:
    """The candidate is read in the addressed frame, not in the page around it."""
    page.goto(f"{fixture_site}/framed.html")
    framed = target(
        {"kind": "role", "value": 'button[name="Save"]'},
        frame=[
            {
                "index": 1,
                "name": "details",
                "url": f"{fixture_site}/frame-details.html",
            }
        ],
    )

    found = resolve(page, framed, Deadline.in_ms(2_000))

    assert isinstance(found, Resolved)
    assert found.locator.get_attribute("id") == "details-save"


def test_a_frame_that_moved_is_still_addressed_by_its_name(
    page: Page, fixture_site: str
) -> None:
    """The recorded position drifted; the name the hop carries still holds."""
    page.goto(f"{fixture_site}/framed-reordered.html")
    framed = target(
        {"kind": "role", "value": 'button[name="Save"]'},
        frame=[{"index": 1, "name": "details"}],
    )

    found = resolve(page, framed, Deadline.in_ms(2_000))

    assert isinstance(found, Resolved)
    assert found.locator.get_attribute("id") == "details-save"


@pytest.mark.parametrize(
    ("candidate", "element_id"),
    [
        ({"kind": "testid", "value": "save-invoice"}, "by-testid"),
        ({"kind": "role", "value": 'button[name="Publish"]'}, "by-role"),
        ({"kind": "placeholder", "value": "Search invoices"}, "by-placeholder"),
        ({"kind": "label", "value": "Email address"}, "by-label"),
        ({"kind": "alt", "value": "Company logo"}, "by-alt"),
        ({"kind": "text", "value": "Overdue since March"}, "by-text"),
        ({"kind": "title", "value": "Copy to clipboard"}, "by-title"),
        ({"kind": "css", "value": "table#by-css"}, "by-css"),
    ],
)
def test_every_candidate_kind_reads_its_own_value(
    page: Page, fixture_site: str, candidate: dict[str, Any], element_id: str
) -> None:
    """What each kind's stored value means — the half the recorder writes to."""
    page.goto(f"{fixture_site}/every-kind.html")

    found = resolve(page, target(candidate), Deadline.in_ms(2_000))

    assert isinstance(found, Resolved)
    assert found.locator.get_attribute("id") == element_id


def test_a_candidate_the_engine_refuses_is_skipped_like_any_other(
    page: Page, fixture_site: str
) -> None:
    """Candidates are hand-editable data: a broken one costs its rank, not the Run."""
    page.goto(f"{fixture_site}/drifted-save.html")
    hand_edited = target(
        {"kind": "css", "value": "#save-button:contains('Save'"},
        {"kind": "role", "value": 'button[name="Save"]'},
    )

    found = resolve(page, hand_edited, Deadline.in_ms(2_000))

    assert isinstance(found, Resolved)
    assert found.rank == 1
