"""The Workflow catalogue at its seam: HTTP against the app, real Postgres.

The list a user lands on, and the four things they do to a Workflow without
opening it. The document store's own tests live in `test_workflows.py`; what
is asserted here is the contract around the document — what a row says before
it is opened, and what listing, renaming, duplicating, and deleting answer.
"""

import json
from base64 import urlsafe_b64encode
from collections.abc import Callable
from typing import Any
from uuid import uuid4

import pytest
from conftest import Account
from test_workflows import (
    a_click_step,
    a_navigate_step,
    a_workflow,
    read_draft,
    save_draft,
)

pytestmark = pytest.mark.integration

NewAccount = Callable[[], Account]


def test_the_list_answers_a_summary_of_every_workflow_the_organization_owns(
    new_account: NewAccount,
) -> None:
    account = new_account()
    a_workflow(account, name="Invoices")
    a_workflow(account, name="Payroll")

    listed = account.client.get("/api/workflows")

    assert listed.status_code == 200, listed.text
    names = {row["name"] for row in listed.json()["items"]}
    assert names == {"Invoices", "Payroll"}


def test_a_row_says_what_it_is_before_it_is_opened(new_account: NewAccount) -> None:
    """Enough to draw the row: what it is called, when it happened, and where
    the Draft stands against what has been published."""
    account = new_account()
    workflow_id = a_workflow(account, name="Invoices")

    never_published = one_row(account, workflow_id)

    assert never_published["draft_state"] == "never-published"
    assert "published_version" not in never_published
    assert never_published["created_at"] <= never_published["last_activity_at"]

    assert (
        save_draft(
            account, workflow_id, steps=[a_navigate_step(str(uuid4()))]
        ).status_code
        == 200
    )
    assert (
        account.client.post(f"/api/workflows/{workflow_id}/versions").status_code == 201
    )

    published = one_row(account, workflow_id)

    assert published["draft_state"] == "in-sync"
    assert published["published_version"] == 1


def one_row(account: Account, workflow_id: str) -> dict[str, Any]:
    """The one summary of this Workflow the list answers with."""
    listed = account.client.get("/api/workflows")
    assert listed.status_code == 200, listed.text
    rows: list[dict[str, Any]] = [
        row for row in listed.json()["items"] if row["id"] == workflow_id
    ]
    assert len(rows) == 1, rows
    return rows[0]


def listed_names(account: Account, **query: object) -> list[str]:
    """The names the list answers with, in the order it answers them."""
    listed = account.client.get("/api/workflows", params=query)
    assert listed.status_code == 200, listed.text
    return [row["name"] for row in listed.json()["items"]]


def test_another_organizations_workflows_are_not_in_the_list(
    new_account: NewAccount,
) -> None:
    account, stranger = new_account(), new_account()
    a_workflow(account, name="Invoices")

    assert listed_names(stranger) == []


def test_the_search_matches_a_name_case_insensitively(new_account: NewAccount) -> None:
    account = new_account()
    for name in ("ACME payroll", "Acme invoices", "Northwind orders"):
        a_workflow(account, name=name)

    assert sorted(listed_names(account, q="acme")) == ["ACME payroll", "Acme invoices"]
    assert listed_names(account, q="northwind") == ["Northwind orders"]


def test_the_search_reads_a_wildcard_as_a_character_to_look_for(
    new_account: NewAccount,
) -> None:
    """`%` is a name a user can type, not a pattern they can inject."""
    account = new_account()
    a_workflow(account, name="Discount 50%")
    a_workflow(account, name="Payroll")

    assert listed_names(account, q="50%") == ["Discount 50%"]
    assert listed_names(account, q="%") == ["Discount 50%"]


def test_the_list_sorts_by_activity_until_it_is_told_otherwise(
    new_account: NewAccount,
) -> None:
    """Activity is what happened to the Workflow, not only what ran it: with no
    Run anywhere, a Workflow orders by its own last-touched time, and editing
    its document is a touch."""
    account = new_account()
    older = a_workflow(account, name="Zebra")
    a_workflow(account, name="Yak")

    assert listed_names(account) == ["Yak", "Zebra"]

    assert (
        save_draft(account, older, steps=[a_navigate_step(str(uuid4()))]).status_code
        == 200
    )

    assert listed_names(account) == ["Zebra", "Yak"]


def test_the_list_sorts_by_name_and_by_creation_when_asked(
    new_account: NewAccount,
) -> None:
    account = new_account()
    for name in ("Payroll", "Acme", "Northwind"):
        a_workflow(account, name=name)

    assert listed_names(account, sort="name") == ["Acme", "Northwind", "Payroll"]
    assert listed_names(account, sort="created") == ["Northwind", "Acme", "Payroll"]


def test_a_sort_the_list_does_not_have_is_refused(new_account: NewAccount) -> None:
    account = new_account()

    refused = account.client.get("/api/workflows", params={"sort": "colour"})

    assert refused.status_code == 422, refused.text


def test_paging_to_exhaustion_yields_every_workflow_once_and_in_order(
    new_account: NewAccount,
) -> None:
    """A keyset cursor rather than an offset: something moves underneath on
    every page, and no row is skipped or served twice because of it."""
    account = new_account()
    ids = {
        name: a_workflow(account, name=name)
        for name in (f"Workflow {number:02d}" for number in range(25))
    }
    moved = ids["Workflow 07"]

    seen: list[dict[str, object]] = []
    cursor: str | None = None
    while True:
        page = account.client.get(
            "/api/workflows",
            params={
                "sort": "name",
                "limit": 10,
                **({"cursor": cursor} if cursor else {}),
            },
        )
        assert page.status_code == 200, page.text
        body = page.json()
        assert len(body["items"]) <= 10
        seen += body["items"]
        assert (
            save_draft(
                account, moved, steps=[a_navigate_step(str(uuid4()))]
            ).status_code
            == 200
        )
        cursor = body.get("next_cursor")
        if cursor is None:
            break

    assert len({row["id"] for row in seen}) == 25
    assert [row["name"] for row in seen] == sorted(ids)


def test_a_cursor_that_did_not_come_from_this_list_is_refused(
    new_account: NewAccount,
) -> None:
    account = new_account()
    a_workflow(account)

    refused = account.client.get("/api/workflows", params={"cursor": "not-a-cursor"})

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "bad_cursor"


def test_a_cursor_is_refused_by_the_order_it_was_not_cut_from(
    new_account: NewAccount,
) -> None:
    """A cursor is a position in one order. Carried into another it would name
    a place that order does not have, and the page after it would be a guess."""
    account = new_account()
    for name in ("Acme", "Northwind"):
        a_workflow(account, name=name)

    first = account.client.get("/api/workflows", params={"sort": "name", "limit": 1})
    cursor = first.json()["next_cursor"]

    refused = account.client.get(
        "/api/workflows", params={"sort": "created", "cursor": cursor}
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "bad_cursor"


def test_a_tampered_cursor_is_refused_rather_than_crashed_on(
    new_account: NewAccount,
) -> None:
    account = new_account()
    a_workflow(account)
    tampered = urlsafe_b64encode(
        json.dumps(
            {"s": "activity", "k": "the beginning of time", "i": str(uuid4())}
        ).encode()
    ).decode()

    refused = account.client.get("/api/workflows", params={"cursor": tampered})

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "bad_cursor"


def test_renaming_a_workflow_changes_what_the_list_calls_it(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account, name="Invoices")

    renamed = account.client.patch(
        f"/api/workflows/{workflow_id}", json={"name": "Invoices, monthly"}
    )

    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Invoices, monthly"
    assert listed_names(account) == ["Invoices, monthly"]


def test_another_organizations_workflow_cannot_be_renamed(
    new_account: NewAccount,
) -> None:
    account, stranger = new_account(), new_account()
    workflow_id = a_workflow(account)

    refused = stranger.client.patch(
        f"/api/workflows/{workflow_id}", json={"name": "Mine now"}
    )

    assert refused.status_code == 404, refused.text
    assert refused.json()["code"] == "workflow_not_found"


def test_a_duplicate_carries_the_steps_across_under_fresh_ids(
    new_account: NewAccount,
) -> None:
    """The document is the same automation; the Step ids are not the same Steps.
    An id is the thread tying a Step to its Results and its Drift, and a copy
    that shared them would tie the copy's history to the original's."""
    account = new_account()
    source = a_workflow(account, name="Invoices")
    steps = [a_navigate_step(str(uuid4())), a_click_step(str(uuid4()))]
    assert (
        save_draft(
            account, source, steps=steps, variables=[{"name": "month"}]
        ).status_code
        == 200
    )

    copied = account.client.post(f"/api/workflows/{source}/duplicate")

    assert copied.status_code == 201, copied.text
    original = read_draft(account, source).json()
    copy = read_draft(account, copied.json()["id"]).json()
    assert [step["id"] for step in copy["steps"]] != [step["id"] for step in steps]
    assert [step["type"] for step in copy["steps"]] == ["navigate", "click"]
    assert [without_id(step) for step in copy["steps"]] == [
        without_id(step) for step in original["steps"]
    ]
    assert copy["variables"] == original["variables"] == [{"name": "month"}]


def without_id(step: dict[str, Any]) -> dict[str, Any]:
    """A Step by everything except the one thing a copy must not share."""
    return {key: value for key, value in step.items() if key != "id"}


def test_a_duplicate_of_a_published_workflow_has_published_nothing(
    new_account: NewAccount,
) -> None:
    account = new_account()
    source = a_workflow(account, name="Invoices")
    assert save_draft(account, source).status_code == 200
    assert account.client.post(f"/api/workflows/{source}/versions").status_code == 201

    copied = account.client.post(f"/api/workflows/{source}/duplicate")

    assert copied.status_code == 201, copied.text
    row = one_row(account, copied.json()["id"])
    assert row["draft_state"] == "never-published"
    assert "published_version" not in row
    assert row["name"] != "Invoices"
    assert (
        account.client.get(f"/api/workflows/{copied.json()['id']}/versions").json()
        == []
    )


def test_another_organizations_workflow_cannot_be_duplicated(
    new_account: NewAccount,
) -> None:
    account, stranger = new_account(), new_account()
    workflow_id = a_workflow(account)

    refused = stranger.client.post(f"/api/workflows/{workflow_id}/duplicate")

    assert refused.status_code == 404, refused.text
    assert refused.json()["code"] == "workflow_not_found"


def test_deleting_a_workflow_takes_its_draft_and_its_versions_with_it(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account, name="Invoices")
    assert save_draft(account, workflow_id).status_code == 200
    assert (
        account.client.post(f"/api/workflows/{workflow_id}/versions").status_code == 201
    )
    kept = a_workflow(account, name="Payroll")

    deleted = account.client.delete(f"/api/workflows/{workflow_id}")

    assert deleted.status_code == 204, deleted.text
    assert read_draft(account, workflow_id).status_code == 404
    assert (
        account.client.get(f"/api/workflows/{workflow_id}/versions").status_code == 404
    )
    assert (
        account.client.get(f"/api/workflows/{workflow_id}/versions/1").status_code
        == 404
    )
    assert [row["id"] for row in listed_rows(account)] == [kept]


def listed_rows(account: Account, **query: object) -> list[dict[str, Any]]:
    """The summaries the list answers with, in the order it answers them."""
    listed = account.client.get("/api/workflows", params=query)
    assert listed.status_code == 200, listed.text
    items: list[dict[str, Any]] = listed.json()["items"]
    return items


def test_another_organizations_workflow_cannot_be_deleted(
    new_account: NewAccount,
) -> None:
    account, stranger = new_account(), new_account()
    workflow_id = a_workflow(account)

    refused = stranger.client.delete(f"/api/workflows/{workflow_id}")

    assert refused.status_code == 404, refused.text
    assert refused.json()["code"] == "workflow_not_found"
    assert len(listed_rows(account)) == 1


def test_one_workflow_reads_back_as_the_row_the_list_would_draw(
    new_account: NewAccount,
) -> None:
    """The Workflow page draws the same header on a reload as the row the user
    clicked. One derivation, so the two cannot disagree about the same Draft."""
    account = new_account()
    workflow_id = a_workflow(account, name="Invoices")
    assert save_draft(account, workflow_id).status_code == 200
    assert (
        account.client.post(f"/api/workflows/{workflow_id}/versions").status_code == 201
    )

    read = account.client.get(f"/api/workflows/{workflow_id}")

    assert read.status_code == 200, read.text
    assert read.json() == one_row(account, workflow_id)


def test_another_organizations_workflow_cannot_be_read(new_account: NewAccount) -> None:
    account, stranger = new_account(), new_account()
    workflow_id = a_workflow(account)

    refused = stranger.client.get(f"/api/workflows/{workflow_id}")

    assert refused.status_code == 404, refused.text
    assert refused.json()["code"] == "workflow_not_found"


def test_a_workflow_says_what_a_step_timeout_falls_back_to(
    new_account: NewAccount,
) -> None:
    """The editor draws a Step with no override of its own as falling back to
    the Workflow's default, and the number in that sentence is this row's —
    never a 30 s the frontend knows by heart."""
    account = new_account()
    workflow_id = a_workflow(account)

    read = account.client.get(f"/api/workflows/{workflow_id}")

    assert read.status_code == 200, read.text
    assert read.json()["default_step_timeout_ms"] == 30_000
