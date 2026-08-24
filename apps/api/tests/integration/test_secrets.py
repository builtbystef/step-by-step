"""The Organization's Secret vault, at its HTTP seam against real Postgres."""

from collections.abc import Callable

import pytest
from conftest import Account, join
from sqlalchemy import text
from step_by_step_core.db import session_scope

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
