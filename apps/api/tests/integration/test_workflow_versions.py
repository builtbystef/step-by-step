"""Publishing at its seam: HTTP against the app, real Postgres.

The Draft's other half. What a publish mints is immutable and self-contained,
what a diff says is keyed on Step ids that outlive it, and the draft state a
list screen and an editor header render is derived from the two, never stored.

The Draft helpers come from the document store's own tests, because a Version
is a Draft that stopped changing and every test here starts by writing one.
"""

from uuid import uuid4

import pytest
from conftest import Account
from httpx import Response
from test_workflows import (
    NewAccount,
    a_click_step,
    a_navigate_step,
    a_workflow,
    read_draft,
    save_draft,
)

pytestmark = pytest.mark.integration


def publish(account: Account, workflow_id: str) -> Response:
    """Mint the next Version, the way the publish modal's confirm does."""
    return account.client.post(f"/api/workflows/{workflow_id}/versions")


def versions(account: Account, workflow_id: str) -> Response:
    return account.client.get(f"/api/workflows/{workflow_id}/versions")


def version(account: Account, workflow_id: str, number: int) -> Response:
    return account.client.get(f"/api/workflows/{workflow_id}/versions/{number}")


def test_publishing_mints_a_version_holding_the_draft_as_it_stands(
    new_account: NewAccount,
) -> None:
    """A Version is executable forever on its own, so it holds the document
    itself — steps and the Variables their values reference — and not a
    reference to a Draft that will have moved on by the time a Run reads it."""
    account = new_account()
    workflow_id = a_workflow(account)
    steps = [a_navigate_step(str(uuid4())), a_click_step(str(uuid4()))]
    save_draft(account, workflow_id, steps=steps)

    published = publish(account, workflow_id)

    assert published.status_code == 201, published.text
    assert published.json()["number"] == 1
    assert (
        version(account, workflow_id, 1).json()
        == read_draft(account, workflow_id).json()
    )


def test_versions_are_numbered_from_one_and_listed_with_their_times(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account)
    save_draft(account, workflow_id, steps=[a_navigate_step(str(uuid4()))])

    first = publish(account, workflow_id).json()["number"]
    save_draft(account, workflow_id, steps=[a_click_step(str(uuid4()))])
    second = publish(account, workflow_id).json()["number"]

    assert [first, second] == [1, 2]
    listed = versions(account, workflow_id)
    assert listed.status_code == 200, listed.text
    assert [entry["number"] for entry in listed.json()] == [1, 2]
    assert all(entry["created_at"] for entry in listed.json())


def test_editing_the_draft_afterwards_leaves_the_version_alone(
    new_account: NewAccount,
) -> None:
    """The whole point of publishing: a Schedule firing at 3 a.m. executes what
    was published, and not what somebody was in the middle of editing."""
    account = new_account()
    workflow_id = a_workflow(account)
    save_draft(account, workflow_id, steps=[a_navigate_step(str(uuid4()))])
    publish(account, workflow_id)
    published = read_draft(account, workflow_id).json()

    save_draft(account, workflow_id, steps=[a_click_step(str(uuid4()))])

    assert version(account, workflow_id, 1).json() == published
    assert read_draft(account, workflow_id).json() != published


def test_no_route_writes_to_a_version(new_account: NewAccount) -> None:
    """Immutability is the absence of a way in, so this is what is asserted:
    the document URL answers reads and refuses every method that would write."""
    account = new_account()
    workflow_id = a_workflow(account)
    save_draft(account, workflow_id, steps=[a_navigate_step(str(uuid4()))])
    publish(account, workflow_id)
    at = f"/api/workflows/{workflow_id}/versions/1"
    document = version(account, workflow_id, 1).json()

    assert account.client.put(at, json=document).status_code == 405
    assert account.client.patch(at, json=document).status_code == 405
    assert account.client.delete(at).status_code == 405
    assert version(account, workflow_id, 1).json() == document


def test_a_version_that_was_never_minted_is_not_found(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account)

    missing = version(account, workflow_id, 1)

    assert missing.status_code == 404, missing.text
    assert missing.json()["code"] == "version_not_found"
    assert versions(account, workflow_id).json() == []


def diff(account: Account, workflow_id: str) -> Response:
    """What publishing would change, as the publish modal asks it."""
    return account.client.get(f"/api/workflows/{workflow_id}/draft/diff")


def a_typed_step(step_id: str, value: str) -> dict[str, object]:
    """A Step whose payload is easy to edit into a different one."""
    return {
        "id": step_id,
        "type": "type",
        "label": "Type the order number",
        "payload": {
            "target": {"candidates": [{"kind": "testid", "value": "order"}]},
            "value": value,
        },
    }


def test_the_diff_is_keyed_on_step_ids_and_not_on_positions(
    new_account: NewAccount,
) -> None:
    """The worked example: with v1 published, A's payload edited, D added, and
    C removed, a publish changes exactly those three Steps. Ids are what make
    that answerable — B and C moved up when A grew, and neither changed."""
    account = new_account()
    workflow_id = a_workflow(account)
    a, b, c, d = (str(uuid4()) for _ in range(4))
    save_draft(
        account,
        workflow_id,
        steps=[a_typed_step(a, "1001"), a_navigate_step(b), a_click_step(c)],
    )
    publish(account, workflow_id)

    save_draft(
        account,
        workflow_id,
        steps=[a_typed_step(a, "2002"), a_navigate_step(b), a_navigate_step(d)],
    )

    changes = diff(account, workflow_id)
    assert changes.status_code == 200, changes.text
    assert [step["id"] for step in changes.json()["changed"]] == [a]
    assert [step["id"] for step in changes.json()["added"]] == [d]
    assert [step["id"] for step in changes.json()["removed"]] == [c]


def test_the_diff_names_each_step_the_way_the_editor_does(
    new_account: NewAccount,
) -> None:
    """A modal saying "3 steps change" tells nobody anything: the labels are
    what the person confirming the publish reads."""
    account = new_account()
    workflow_id = a_workflow(account)
    removed, added = str(uuid4()), str(uuid4())
    save_draft(account, workflow_id, steps=[a_click_step(removed)])
    publish(account, workflow_id)

    save_draft(account, workflow_id, steps=[a_navigate_step(added)])

    changes = diff(account, workflow_id).json()
    assert changes["removed"] == [{"id": removed, "label": "Click Save"}]
    assert changes["added"] == [{"id": added, "label": "Go to the invoice list"}]


def test_a_first_publish_shows_every_step_as_added(new_account: NewAccount) -> None:
    """There is nothing to compare against, so the modal that opens over a
    never-published Workflow shows the whole Workflow arriving."""
    account = new_account()
    workflow_id = a_workflow(account)
    steps = [a_navigate_step(str(uuid4())), a_click_step(str(uuid4()))]
    save_draft(account, workflow_id, steps=steps)

    changes = diff(account, workflow_id).json()

    assert [step["id"] for step in changes["added"]] == [step["id"] for step in steps]
    assert changes["changed"] == []
    assert changes["removed"] == []


def state(account: Account, workflow_id: str) -> str:
    """The Draft chip's word, as the editor header derives it."""
    return str(diff(account, workflow_id).json()["state"])


def test_the_draft_state_follows_publishing_and_editing(
    new_account: NewAccount,
) -> None:
    """The three states in the order a Workflow lives through them."""
    account = new_account()
    workflow_id = a_workflow(account)
    save_draft(account, workflow_id, steps=[a_navigate_step(str(uuid4()))])

    assert state(account, workflow_id) == "never-published"
    assert diff(account, workflow_id).json()["latest_version"] is None

    publish(account, workflow_id)

    assert state(account, workflow_id) == "in-sync"
    assert diff(account, workflow_id).json()["latest_version"] == 1

    save_draft(account, workflow_id, steps=[a_click_step(str(uuid4()))])

    assert state(account, workflow_id) == "unpublished-changes"

    publish(account, workflow_id)

    assert state(account, workflow_id) == "in-sync"
    assert diff(account, workflow_id).json()["latest_version"] == 2


def test_a_draft_saved_back_unchanged_is_still_in_sync(
    new_account: NewAccount,
) -> None:
    """A save is not an edit. An editor that opens a Workflow and writes the
    same document back must not turn a green chip amber."""
    account = new_account()
    workflow_id = a_workflow(account)
    steps = [a_navigate_step(str(uuid4()))]
    save_draft(account, workflow_id, steps=steps)
    publish(account, workflow_id)

    save_draft(account, workflow_id, steps=steps)

    assert state(account, workflow_id) == "in-sync"


def test_a_change_no_step_diff_can_show_is_still_unpublished_changes(
    new_account: NewAccount,
) -> None:
    """Renaming nothing and reordering two Steps changes what a Run does — the
    order it acts in, and which values are masked — so the chip says so even
    though no Step was added, changed, or removed."""
    account = new_account()
    workflow_id = a_workflow(account)
    first, second = a_navigate_step(str(uuid4())), a_click_step(str(uuid4()))
    save_draft(account, workflow_id, steps=[first, second])
    publish(account, workflow_id)

    save_draft(
        account,
        workflow_id,
        steps=[second, first],
        variables=[{"name": "tenant", "secret": True}],
    )

    changes = diff(account, workflow_id).json()
    assert changes["state"] == "unpublished-changes"
    assert (changes["added"], changes["changed"], changes["removed"]) == ([], [], [])


def restore(account: Account, workflow_id: str, number: int) -> Response:
    """Bring a past Version back into the Draft, as the editor's restore does."""
    return account.client.post(
        f"/api/workflows/{workflow_id}/versions/{number}/restore"
    )


def test_restoring_a_version_puts_its_document_back_in_the_draft(
    new_account: NewAccount,
) -> None:
    """Ids come back as they went in: a restored Step is the same Step, so its
    Step Results across the Versions in between are still its own history."""
    account = new_account()
    workflow_id = a_workflow(account)
    old, new = str(uuid4()), str(uuid4())
    save_draft(account, workflow_id, steps=[a_navigate_step(old)])
    publish(account, workflow_id)
    first = version(account, workflow_id, 1).json()
    save_draft(account, workflow_id, steps=[a_click_step(new)])
    publish(account, workflow_id)

    restored = restore(account, workflow_id, 1)

    assert restored.status_code == 200, restored.text
    assert restored.json() == first
    assert read_draft(account, workflow_id).json() == first
    assert [
        step["id"] for step in read_draft(account, workflow_id).json()["steps"]
    ] == [old]


def test_restoring_mints_nothing_and_changes_no_version(
    new_account: NewAccount,
) -> None:
    """Restoring is an edit of the Draft. What executes is unchanged until the
    user publishes what they restored, which is what the chip then asks for."""
    account = new_account()
    workflow_id = a_workflow(account)
    save_draft(account, workflow_id, steps=[a_navigate_step(str(uuid4()))])
    publish(account, workflow_id)
    first = version(account, workflow_id, 1).json()
    save_draft(account, workflow_id, steps=[a_click_step(str(uuid4()))])
    publish(account, workflow_id)
    second = version(account, workflow_id, 2).json()

    restore(account, workflow_id, 1)

    assert [entry["number"] for entry in versions(account, workflow_id).json()] == [
        1,
        2,
    ]
    assert version(account, workflow_id, 1).json() == first
    assert version(account, workflow_id, 2).json() == second
    assert state(account, workflow_id) == "unpublished-changes"


def test_restoring_the_latest_version_leaves_the_draft_in_sync(
    new_account: NewAccount,
) -> None:
    """The state is a comparison and not a memory of what was done to get here:
    a Draft that has been edited back to the latest Version is in sync."""
    account = new_account()
    workflow_id = a_workflow(account)
    save_draft(account, workflow_id, steps=[a_navigate_step(str(uuid4()))])
    publish(account, workflow_id)
    save_draft(account, workflow_id, steps=[a_click_step(str(uuid4()))])

    restore(account, workflow_id, 1)

    assert state(account, workflow_id) == "in-sync"


def test_restoring_a_version_that_does_not_exist_leaves_the_draft_alone(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account)
    save_draft(account, workflow_id, steps=[a_navigate_step(str(uuid4()))])
    editing = read_draft(account, workflow_id).json()

    refused = restore(account, workflow_id, 7)

    assert refused.status_code == 404, refused.text
    assert refused.json()["code"] == "version_not_found"
    assert read_draft(account, workflow_id).json() == editing


def test_another_organizations_versions_do_not_exist(new_account: NewAccount) -> None:
    """Same rule as the Draft's, on every route that arrived with publishing:
    a refusal that admitted the id exists would map another tenant's Workflows
    one guess at a time."""
    owner = new_account()
    workflow_id = a_workflow(owner)
    save_draft(owner, workflow_id, steps=[a_navigate_step(str(uuid4()))])
    publish(owner, workflow_id)
    stranger = new_account()

    refusals = [
        publish(stranger, workflow_id),
        versions(stranger, workflow_id),
        version(stranger, workflow_id, 1),
        restore(stranger, workflow_id, 1),
        diff(stranger, workflow_id),
    ]

    assert [refused.status_code for refused in refusals] == [404] * 5
    assert {refused.json()["code"] for refused in refusals} == {"workflow_not_found"}
    assert [entry["number"] for entry in versions(owner, workflow_id).json()] == [1]
