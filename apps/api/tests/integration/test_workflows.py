"""The Workflow document store at its seam: HTTP against the app, real Postgres.

External behaviour only. A Workflow is created, its Draft is read and saved,
and every refusal is read by the machine-readable `code` a client acts on.
"""

from collections.abc import Callable
from uuid import uuid4

import pytest
from conftest import Account
from httpx import Response

pytestmark = pytest.mark.integration

NewAccount = Callable[[], Account]


def a_workflow(account: Account, name: str = "Invoices") -> str:
    """A Workflow of this account's own, and the id its Draft hangs off."""
    created = account.client.post("/api/workflows", json={"name": name})
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


def a_navigate_step(step_id: str) -> dict[str, object]:
    """The simplest Step there is: one that goes somewhere."""
    return {
        "id": step_id,
        "type": "navigate",
        "label": "Go to the invoice list",
        "payload": {"url": "https://example.test/invoices"},
    }


def a_click_step(step_id: str) -> dict[str, object]:
    """A Step that finds an element, which is what most Steps do."""
    return {
        "id": step_id,
        "type": "click",
        "label": "Click Save",
        "payload": {
            "target": {
                "candidates": [
                    {"kind": "testid", "value": "save"},
                    {"kind": "role", "value": "button[name='Save']"},
                ]
            }
        },
    }


def save_draft(account: Account, workflow_id: str, **document: object) -> Response:
    """Replace a Draft, the way the editor's save does."""
    body = {"steps": [], "variables": [], **document}
    return account.client.put(f"/api/workflows/{workflow_id}/draft", json=body)


def read_draft(account: Account, workflow_id: str) -> Response:
    return account.client.get(f"/api/workflows/{workflow_id}/draft")


def test_creating_a_workflow_starts_it_with_an_empty_draft(
    new_account: NewAccount,
) -> None:
    account = new_account()

    created = account.client.post("/api/workflows", json={"name": "Invoices"})

    assert created.status_code == 201, created.text
    workflow = created.json()
    assert workflow["name"] == "Invoices"
    assert workflow["default_step_timeout_ms"] == 30_000
    assert workflow["takeover_timeout_ms"] == 1_800_000

    draft = account.client.get(f"/api/workflows/{workflow['id']}/draft")

    assert draft.status_code == 200, draft.text
    assert draft.json() == {"steps": [], "variables": []}


def test_a_sparse_step_round_trips_without_materializing_defaults(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account)
    sparse = {"steps": [a_navigate_step(str(uuid4()))], "variables": []}

    saved = account.client.put(f"/api/workflows/{workflow_id}/draft", json=sparse)

    assert saved.status_code == 200, saved.text
    assert saved.json() == sparse
    assert read_draft(account, workflow_id).json() == sparse


def test_a_save_replaces_the_draft_whole_and_rewrites_no_step_id(
    new_account: NewAccount,
) -> None:
    """Ids are the thread between Versions, Step Results, and Selector Drift:
    a save that renumbered them would break every one of those on the way past."""
    account = new_account()
    workflow_id = a_workflow(account)
    first, second = str(uuid4()), str(uuid4())

    saved = save_draft(
        account, workflow_id, steps=[a_navigate_step(first), a_click_step(second)]
    )

    assert saved.status_code == 200, saved.text
    assert [step["id"] for step in saved.json()["steps"]] == [first, second]

    shortened = save_draft(account, workflow_id, steps=[a_click_step(second)])

    assert [step["id"] for step in shortened.json()["steps"]] == [second]
    assert read_draft(account, workflow_id).json() == shortened.json()


def test_a_duplicate_step_id_is_refused_and_the_error_names_it(
    new_account: NewAccount,
) -> None:
    """The database cannot see inside the JSONB, so the save is the only place
    this can be caught — and the id has to be in the message, or an editor
    holding two hundred Steps cannot say which one it is."""
    account = new_account()
    workflow_id = a_workflow(account)
    twice = str(uuid4())

    refused = save_draft(
        account, workflow_id, steps=[a_navigate_step(twice), a_click_step(twice)]
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "duplicate_step_id"
    assert twice in refused.json()["message"]
    assert read_draft(account, workflow_id).json()["steps"] == []


def test_a_duplicate_variable_name_is_refused_and_the_error_names_it(
    new_account: NewAccount,
) -> None:
    """Secret masking keys off the Variable's secret flag, so a name declared
    twice with two flags decides by whichever row a reader happens to pick
    whether the value is masked in a form, in logs, and in a Batch's rows."""
    account = new_account()
    workflow_id = a_workflow(account)

    refused = save_draft(
        account,
        workflow_id,
        variables=[
            {"name": "password", "secret": True},
            {"name": "password", "secret": False},
        ],
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "duplicate_variable_name"
    assert "password" in refused.json()["message"]
    assert read_draft(account, workflow_id).json()["variables"] == []


def test_variable_names_that_differ_only_in_case_are_two_variables(
    new_account: NewAccount,
) -> None:
    """`{{name}}` interpolation matches exactly, so folding the comparison here
    would refuse a document whose two references do resolve to two values."""
    account = new_account()
    workflow_id = a_workflow(account)
    declared = [{"name": "Password", "secret": True}, {"name": "password"}]

    saved = save_draft(account, workflow_id, variables=declared)

    assert saved.status_code == 200, saved.text
    assert [variable["name"] for variable in saved.json()["variables"]] == [
        "Password",
        "password",
    ]


def a_target(**over: object) -> dict[str, object]:
    """A ranked candidate list, best-first, as the recorder verified it."""
    return {
        "candidates": [
            {"kind": "testid", "value": "total"},
            {"kind": "css", "value": "#total", "shadowPath": ["#card"]},
        ],
        **over,
    }


def a_step(
    step_id: str, step_type: str, payload: dict[str, object]
) -> dict[str, object]:
    """A Step with every envelope field said out loud, so a round trip is exact."""
    return {
        "id": step_id,
        "type": step_type,
        "label": f"The {step_type} step",
        "optional": False,
        "disabled": False,
        "screenshot": step_type == "extract",
        "timeoutMs": 45_000,
        "payload": payload,
    }


def every_step_type() -> list[dict[str, object]]:
    """One Step of each of the eight types, plus both modes that branch."""
    return [
        a_step(str(uuid4()), "navigate", {"url": "https://example.test/{{account}}"}),
        a_step(
            str(uuid4()),
            "click",
            {
                "target": a_target(
                    frame=[{"index": 0, "name": "checkout", "url": "https://pay.test/"}]
                ),
                "assertedNavigation": True,
            },
        ),
        a_step(str(uuid4()), "type", {"target": a_target(), "value": "{{password}}"}),
        a_step(str(uuid4()), "select", {"target": a_target(), "value": "Paid"}),
        a_step(
            str(uuid4()),
            "download",
            {
                "target": a_target(
                    unsupported={
                        "reason": "closed-shadow-root",
                        "warning": "This part of the page is sealed off.",
                    }
                )
            },
        ),
        a_step(
            str(uuid4()),
            "extract",
            {
                "target": a_target(),
                "outputName": "total",
                "mode": "scalar",
                "attribute": "data-total",
            },
        ),
        a_step(
            str(uuid4()),
            "extract",
            {
                "target": a_target(),
                "outputName": "rows",
                "mode": "list",
                "fields": [
                    {"name": "sku", "subSelector": ".sku"},
                    {"name": "href", "subSelector": "a", "attribute": "href"},
                ],
            },
        ),
        a_step(str(uuid4()), "wait", {"mode": "duration", "durationMs": 1_500}),
        a_step(str(uuid4()), "wait", {"mode": "element", "target": a_target()}),
        a_step(
            str(uuid4()),
            "pause-for-takeover",
            {
                "message": "Solve the captcha, then hand it back",
                "timeoutMs": 600_000,
                "successCheck": a_target(),
            },
        ),
    ]


def test_a_draft_holds_every_step_type_with_its_payload(
    new_account: NewAccount,
) -> None:
    """All eight types in one document, because one Workflow may hold all eight —
    including the `screenshot` flag and the pause's `successCheck`."""
    account = new_account()
    workflow_id = a_workflow(account)
    steps = every_step_type()
    variables = [
        {"name": "account", "secret": False},
        {"name": "password", "secret": True},
    ]

    saved = save_draft(account, workflow_id, steps=steps, variables=variables)

    assert saved.status_code == 200, saved.text
    assert saved.json() == {"steps": steps, "variables": variables}
    assert read_draft(account, workflow_id).json() == {
        "steps": steps,
        "variables": variables,
    }


def test_a_step_type_nobody_can_execute_is_refused(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id = a_workflow(account)

    refused = save_draft(
        account,
        workflow_id,
        steps=[a_step(str(uuid4()), "teleport", {"url": "https://example.test/"})],
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "unknown_step_type"


def test_a_payload_that_does_not_fit_its_type_is_refused(
    new_account: NewAccount,
) -> None:
    """A click with nothing to click is not a Step a Worker could ever walk."""
    account = new_account()
    workflow_id = a_workflow(account)

    refused = save_draft(
        account,
        workflow_id,
        steps=[a_step(str(uuid4()), "click", {"url": "https://example.test/"})],
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "malformed_payload"


def test_a_value_referencing_a_variable_nothing_declares_is_refused(
    new_account: NewAccount,
) -> None:
    """This is how the editor's "you cannot delete a Variable a Step uses" is
    kept true no matter who is writing: the document that lost the declaration
    is the document that is refused."""
    account = new_account()
    workflow_id = a_workflow(account)
    typing = a_step(
        str(uuid4()), "type", {"target": a_target(), "value": "{{password}}"}
    )
    declared = [{"name": "password", "secret": True}]
    assert (
        save_draft(account, workflow_id, steps=[typing], variables=declared).status_code
        == 200
    )

    refused = save_draft(account, workflow_id, steps=[typing], variables=[])

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "undeclared_variable"
    assert "password" in refused.json()["message"]
    assert read_draft(account, workflow_id).json()["variables"] == declared


def test_a_navigate_url_may_mix_literal_text_and_variables(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account)
    going = a_step(
        str(uuid4()), "navigate", {"url": "https://example.test/{{tenant}}/invoices"}
    )

    refused = save_draft(account, workflow_id, steps=[going], variables=[])

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "undeclared_variable"
    assert "tenant" in refused.json()["message"]
    assert (
        save_draft(
            account, workflow_id, steps=[going], variables=[{"name": "tenant"}]
        ).status_code
        == 200
    )


def test_another_organizations_workflow_does_not_exist(
    new_account: NewAccount,
) -> None:
    """404 and not 403: a refusal that admitted the id exists would let anyone
    map another tenant's Workflows one guess at a time."""
    owner = new_account()
    workflow_id = a_workflow(owner)
    save_draft(owner, workflow_id, steps=[a_navigate_step(str(uuid4()))])
    stranger = new_account()

    read = read_draft(stranger, workflow_id)
    written = save_draft(stranger, workflow_id, steps=[])

    assert read.status_code == 404, read.text
    assert read.json()["code"] == "workflow_not_found"
    assert written.status_code == 404, written.text
    assert len(read_draft(owner, workflow_id).json()["steps"]) == 1


def test_acting_in_an_organization_you_are_not_in_is_refused(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    workflow_id = a_workflow(owner)
    stranger = new_account()
    stranger.client.headers["X-Organization"] = owner.org_id

    refused = read_draft(stranger, workflow_id)

    assert refused.status_code == 403, refused.text
    assert refused.json()["code"] == "not_a_member"


def test_a_request_that_names_no_organization_is_refused(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account)
    del account.client.headers["X-Organization"]

    refused = read_draft(account, workflow_id)

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "organization_required"


def test_a_signed_out_visitor_reaches_no_workflow(new_account: NewAccount) -> None:
    account = new_account()
    workflow_id = a_workflow(account)
    account.client.post("/api/auth/logout")

    refused = read_draft(account, workflow_id)

    assert refused.status_code == 401, refused.text
    assert refused.json()["code"] == "unauthenticated"


def test_the_editor_clears_a_field_by_writing_it_as_null(
    new_account: NewAccount,
) -> None:
    """The editor edits the document it read and sends it back whole, so a
    field a person emptied travels as an explicit null rather than vanishing
    from the object. It is accepted, and it reads back the way absence always
    reads back here: absent."""
    account = new_account()
    workflow_id = a_workflow(account)
    step_id = str(uuid4())

    saved = save_draft(
        account,
        workflow_id,
        steps=[
            {
                "id": step_id,
                "type": "pause-for-takeover",
                "label": "Pause for a person",
                "optional": False,
                "disabled": False,
                "timeoutMs": None,
                "payload": {"message": None, "timeoutMs": None, "successCheck": None},
            }
        ],
    )

    assert saved.status_code == 200, saved.text
    step = saved.json()["steps"][0]
    assert step["id"] == step_id
    assert "timeoutMs" not in step
    assert step["payload"] == {}


def test_a_secret_variable_may_bind_to_a_vault_entry(
    new_account: NewAccount,
) -> None:
    """The pointer is the Secret's id; the name is cached for display."""
    account = new_account()
    workflow_id = a_workflow(account)
    secret_id = str(uuid4())
    bound = [
        {
            "name": "password",
            "secret": True,
            "secretId": secret_id,
            "secretName": "acme-portal-password",
        }
    ]

    saved = save_draft(account, workflow_id, variables=bound)

    assert saved.status_code == 200, saved.text
    assert saved.json()["variables"] == bound
    assert read_draft(account, workflow_id).json()["variables"] == bound


def test_a_non_secret_variable_may_not_carry_a_vault_pointer(
    new_account: NewAccount,
) -> None:
    account = new_account()
    workflow_id = a_workflow(account)

    refused = save_draft(
        account,
        workflow_id,
        variables=[
            {
                "name": "tenant",
                "secret": False,
                "secretId": str(uuid4()),
                "secretName": "acme-portal-password",
            }
        ],
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "malformed_payload"
    assert "secretId" in refused.json()["message"]
    assert read_draft(account, workflow_id).json()["variables"] == []
