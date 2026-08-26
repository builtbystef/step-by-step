"""The Organization's Secret vault, at its HTTP seam against real Postgres."""

from collections.abc import Callable

import pytest
from conftest import Account, join
from sqlalchemy import text
from step_by_step_core.db import session_scope
from test_workflow_versions import publish
from test_workflows import a_workflow, save_draft

pytestmark = pytest.mark.integration
NewAccount = Callable[[], Account]


def create(actor: Account, name: str = "Portal password", value: str = "open-sesame"):
    return actor.client.post("/api/secrets", json={"name": name, "value": value})


def test_names_are_unique_inside_one_organization(new_account: NewAccount) -> None:
    first = new_account()
    second = new_account()

    made = create(first)
    duplicate = create(first, value="another")
    other_tenant = create(second)

    assert made.status_code == 201, made.text
    assert duplicate.status_code == 409, duplicate.text
    assert duplicate.json()["code"] == "name_taken"
    assert other_tenant.status_code == 201, other_tenant.text


def test_values_and_personal_overrides_are_stored_only_as_sealed_blobs(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    secret = create(owner, value="org-plaintext-fragment").json()
    overridden = owner.client.put(
        f"/api/secrets/{secret['id']}/override",
        json={"value": "personal-plaintext-fragment"},
    )
    assert overridden.status_code == 204, overridden.text

    with session_scope() as db:
        rows = db.execute(
            text(
                "SELECT sealed_value, sealed_data_key FROM secrets WHERE id = :id "
                "UNION ALL SELECT sealed_value, sealed_data_key FROM secret_overrides "
                "WHERE secret_id = :id"
            ),
            {"id": secret["id"]},
        ).all()

    assert len(rows) == 2
    stored = b"".join(blob for row in rows for blob in row)
    assert b"org-plaintext-fragment" not in stored
    assert b"personal-plaintext-fragment" not in stored


def test_patch_preserves_or_replaces_the_value_and_moves_updated_at(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    secret = create(owner, value="first-value").json()
    before = owner.client.get("/api/secrets").json()[0]["updated_at"]

    renamed = owner.client.patch(
        f"/api/secrets/{secret['id']}", json={"name": "Renamed"}
    )
    reveal_after_rename = owner.client.post(f"/api/secrets/{secret['id']}/reveal")
    replaced = owner.client.patch(
        f"/api/secrets/{secret['id']}", json={"value": "second-value"}
    )
    after = owner.client.get("/api/secrets").json()[0]["updated_at"]

    assert renamed.status_code == 200, renamed.text
    assert reveal_after_rename.json() == {"value": "first-value"}
    assert replaced.status_code == 200, replaced.text
    assert owner.client.post(f"/api/secrets/{secret['id']}/reveal").json() == {
        "value": "second-value"
    }
    assert after > before


def test_delete_cascades_overrides_and_a_second_delete_is_not_found(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    member = join(owner, new_account())
    secret = create(owner).json()
    assert (
        member.client.put(
            f"/api/secrets/{secret['id']}/override", json={"value": "mine"}
        ).status_code
        == 204
    )

    deleted = owner.client.delete(f"/api/secrets/{secret['id']}")
    again = owner.client.delete(f"/api/secrets/{secret['id']}")

    assert deleted.status_code == 204, deleted.text
    assert again.status_code == 404, again.text
    with session_scope() as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM secret_overrides WHERE secret_id = :id"),
                {"id": secret["id"]},
            ).scalar_one()
            == 0
        )


def test_every_secret_endpoint_hides_ids_outside_the_active_organization(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    outsider = new_account()
    secret = create(owner).json()
    join(outsider, owner)
    paths = [
        ("patch", f"/api/secrets/{secret['id']}", {"json": {"name": "No"}}),
        ("delete", f"/api/secrets/{secret['id']}", {}),
        ("post", f"/api/secrets/{secret['id']}/reveal", {}),
        ("put", f"/api/secrets/{secret['id']}/override", {"json": {"value": "No"}}),
        ("delete", f"/api/secrets/{secret['id']}/override", {}),
        ("post", f"/api/secrets/{secret['id']}/override/reveal", {}),
    ]

    for method, path, kwargs in paths:
        answer = getattr(outsider.client, method)(path, **kwargs)
        assert answer.status_code == 404, (method, path, answer.text)

    owner.client.headers["X-Organization"] = outsider.org_id
    assert owner.client.post(f"/api/secrets/{secret['id']}/reveal").status_code == 404


def test_reveal_requires_only_a_signed_in_member(new_account: NewAccount) -> None:
    owner = new_account()
    member = join(owner, new_account())
    secret = create(owner, value="shared").json()

    assert member.client.post(f"/api/secrets/{secret['id']}/reveal").json() == {
        "value": "shared"
    }
    member.client.cookies.clear()
    assert member.client.post(f"/api/secrets/{secret['id']}/reveal").status_code == 401


def test_personal_override_is_visible_and_revealed_only_to_its_holder(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    member = join(owner, new_account())
    secret = create(owner, value="shared").json()

    set_own = owner.client.put(
        f"/api/secrets/{secret['id']}/override", json={"value": "only-mine"}
    )

    assert set_own.status_code == 204, set_own.text
    assert owner.client.get("/api/secrets").json()[0]["my_override"] is not None
    assert member.client.get("/api/secrets").json()[0]["my_override"] is None
    assert owner.client.post(f"/api/secrets/{secret['id']}/override/reveal").json() == {
        "value": "only-mine"
    }
    assert owner.client.post(f"/api/secrets/{secret['id']}/reveal").json() == {
        "value": "shared"
    }
    assert (
        member.client.post(f"/api/secrets/{secret['id']}/override/reveal").json()[
            "code"
        ]
        == "no_override"
    )
    assert (
        owner.client.delete(f"/api/secrets/{secret['id']}/override").status_code == 204
    )
    missing = owner.client.post(f"/api/secrets/{secret['id']}/override/reveal")
    assert missing.status_code == 404
    assert missing.json()["code"] == "no_override"


def test_ending_the_organization_cascades_the_whole_secret_vault(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    secret = create(owner).json()
    assert (
        owner.client.put(
            f"/api/secrets/{secret['id']}/override", json={"value": "mine"}
        ).status_code
        == 204
    )
    me = owner.client.get("/api/auth/me").json()
    name = next(org["name"] for org in me["orgs"] if org["id"] == owner.org_id)

    ended = owner.client.request(
        "DELETE",
        f"/api/orgs/{owner.org_id}",
        json={"name_confirmation": name},
    )

    assert ended.status_code == 204, ended.text
    with session_scope() as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM secrets WHERE id = :id"),
                {"id": secret["id"]},
            ).scalar_one()
            == 0
        )
        assert (
            db.execute(
                text("SELECT count(*) FROM secret_overrides WHERE secret_id = :id"),
                {"id": secret["id"]},
            ).scalar_one()
            == 0
        )


def bind(
    actor: Account,
    workflow_id: str,
    secret: dict[str, object],
    name: str = "password",
) -> None:
    """Point a secret Variable at this vault entry."""
    saved = save_draft(
        actor,
        workflow_id,
        variables=[
            {
                "name": name,
                "secret": True,
                "secretId": secret["id"],
                "secretName": secret["name"],
            }
        ],
    )
    assert saved.status_code == 200, saved.text


def used_by(actor: Account, secret_id: str) -> list[dict[str, object]]:
    listed = actor.client.get("/api/secrets").json()
    return next(row["used_by"] for row in listed if row["id"] == secret_id)


def test_used_by_lists_each_bound_workflow_and_drops_one_that_unbinds(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    secret = create(owner, name="acme-portal-password").json()
    invoices = a_workflow(owner, "Invoices")
    payroll = a_workflow(owner, "Payroll")
    bind(owner, invoices, secret)
    bind(owner, payroll, secret)

    both = used_by(owner, secret["id"])

    assert {row["workflow_id"] for row in both} == {invoices, payroll}
    assert {row["workflow_name"] for row in both} == {"Invoices", "Payroll"}

    save_draft(owner, invoices, variables=[{"name": "password", "secret": True}])
    remaining = used_by(owner, secret["id"])
    assert remaining == [{"workflow_id": payroll, "workflow_name": "Payroll"}]


def test_renaming_a_secret_leaves_every_binding_pointing_at_its_id(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    secret = create(owner, name="acme-portal-password").json()
    workflow_id = a_workflow(owner, "Invoices")
    bind(owner, workflow_id, secret)
    publish(owner, workflow_id)

    renamed = owner.client.patch(
        f"/api/secrets/{secret['id']}", json={"name": "portal-password"}
    )
    draft = owner.client.get(f"/api/workflows/{workflow_id}/draft").json()
    version = owner.client.get(f"/api/workflows/{workflow_id}/versions/1").json()
    listed = owner.client.get("/api/secrets").json()[0]

    assert renamed.status_code == 200, renamed.text
    assert draft["variables"][0]["secretId"] == secret["id"]
    assert version["variables"][0]["secretId"] == secret["id"]
    assert listed["name"] == "portal-password"
    assert listed["used_by"] == [
        {"workflow_id": workflow_id, "workflow_name": "Invoices"}
    ]


def test_deleting_a_bound_secret_does_not_block_and_leaves_the_document(
    new_account: NewAccount,
) -> None:
    """No blocking delete, no zombie rows. The Draft keeps the cached name."""
    owner = new_account()
    secret = create(owner, name="acme-portal-password").json()
    workflow_id = a_workflow(owner, "Invoices")
    bind(owner, workflow_id, secret)
    bound = owner.client.get(f"/api/workflows/{workflow_id}/draft").json()

    deleted = owner.client.delete(f"/api/secrets/{secret['id']}")
    draft = owner.client.get(f"/api/workflows/{workflow_id}/draft")
    resaved = save_draft(owner, workflow_id, **bound)

    assert deleted.status_code == 204, deleted.text
    assert owner.client.get("/api/secrets").json() == []
    assert draft.json() == bound
    assert draft.json()["variables"][0]["secretName"] == "acme-portal-password"
    assert resaved.status_code == 200, resaved.text
    with session_scope() as db:
        assert (
            db.execute(
                text("SELECT count(*) FROM secrets WHERE id = :id"),
                {"id": secret["id"]},
            ).scalar_one()
            == 0
        )


def test_a_workflow_bound_only_in_a_version_still_counts(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    secret = create(owner).json()
    workflow_id = a_workflow(owner, "Invoices")
    bind(owner, workflow_id, secret)
    publish(owner, workflow_id)
    save_draft(owner, workflow_id, variables=[])

    assert used_by(owner, secret["id"]) == [
        {"workflow_id": workflow_id, "workflow_name": "Invoices"}
    ]


def test_used_by_does_not_list_another_organizations_workflow(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    other = new_account()
    secret = create(owner).json()
    bind(
        other,
        a_workflow(other, "Theirs"),
        {"id": secret["id"], "name": secret["name"]},
    )

    assert used_by(owner, secret["id"]) == []
