"""Auth State at its store and signed-in HTTP seams against real Postgres."""

from collections.abc import Callable
from datetime import timedelta
from uuid import UUID

import pytest
from conftest import Account, join
from sqlalchemy import select, text
from step_by_step_api import clock
from step_by_step_api.accounts.models import User
from step_by_step_api.auth_states.blob import AuthStateBlob
from step_by_step_api.auth_states.models import AuthState
from step_by_step_api.auth_states.store import store
from step_by_step_core.db import session_scope

pytestmark = pytest.mark.integration
NewAccount = Callable[[], Account]


def blob(domain: str, cookie_value: str) -> AuthStateBlob:
    return AuthStateBlob.model_validate(
        {
            "domain": domain,
            "cookies": [
                {
                    "name": "session",
                    "value": cookie_value,
                    "domain": f".{domain}",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "Lax",
                    "partitionKey": {"topLevelSite": f"https://{domain}"},
                }
            ],
            "origins": [
                {
                    "origin": f"https://app.{domain}",
                    "local_storage": [{"name": "token", "value": "local-secret"}],
                }
            ],
            "session_storage": [
                {
                    "origin": f"https://app.{domain}",
                    "items": [{"name": "state", "value": "session-secret"}],
                }
            ],
        }
    )


def user_id(account: Account) -> UUID:
    with session_scope() as db:
        return db.execute(
            select(User.id).where(User.email == account.email)
        ).scalar_one()


def test_store_upserts_each_layer_without_exposing_blob_contents(
    new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = new_account()
    member = join(owner, new_account())

    with session_scope() as db:
        organization = store(
            db, UUID(owner.org_id), None, blob("example.com", "org-old")
        )
        personal = store(
            db, UUID(owner.org_id), user_id(member), blob("example.com", "personal")
        )
        personal_only = store(
            db, UUID(owner.org_id), user_id(member), blob("github.io", "only-mine")
        )
        db.commit()
        db.refresh(organization)
        created_at = organization.created_at
        old_updated_at = organization.updated_at
        organization_id = organization.id
        personal_id = personal.id
        personal_only_id = personal_only.id

    monkeypatch.setattr(clock, "now", lambda: old_updated_at + timedelta(minutes=1))
    with session_scope() as db:
        replaced = store(db, UUID(owner.org_id), None, blob("example.com", "org-new"))
        db.commit()
        db.refresh(replaced)
        assert replaced.id == organization_id
        assert replaced.created_at == created_at
        assert replaced.updated_at > old_updated_at

    with session_scope() as db:
        rows = (
            db.execute(select(AuthState).where(AuthState.org_id == UUID(owner.org_id)))
            .scalars()
            .all()
        )
        raw = db.execute(
            text(
                "SELECT sealed_blob, sealed_data_key FROM auth_states "
                "WHERE org_id = :org_id"
            ),
            {"org_id": owner.org_id},
        ).all()

    assert {row.id for row in rows} == {organization_id, personal_id, personal_only_id}
    stored_bytes = b"".join(value for row in raw for value in row)
    for plaintext in (
        b"org-old",
        b"org-new",
        b"personal",
        b"only-mine",
        b"local-secret",
        b"session-secret",
    ):
        assert plaintext not in stored_bytes


def test_list_and_forget_are_scoped_to_the_active_member_and_organization(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    member = join(owner, new_account())
    other_member = join(owner, new_account())
    outsider = new_account()
    with session_scope() as db:
        organization = store(db, UUID(owner.org_id), None, blob("example.com", "org"))
        own = store(
            db, UUID(owner.org_id), user_id(member), blob("personal.test", "own")
        )
        another_person = store(
            db,
            UUID(owner.org_id),
            user_id(other_member),
            blob("other.test", "other"),
        )
        another_org = store(
            db, UUID(outsider.org_id), None, blob("outside.test", "outside")
        )
        db.commit()
        ids = {
            "organization": str(organization.id),
            "own": str(own.id),
            "another_person": str(another_person.id),
            "another_org": str(another_org.id),
        }

    listed = member.client.get("/api/auth-states")

    assert listed.status_code == 200, listed.text
    assert {(row["domain"], row["scope"]) for row in listed.json()} == {
        ("example.com", "organization"),
        ("personal.test", "personal"),
    }
    assert all(
        set(row) == {"id", "domain", "scope", "created_at", "updated_at"}
        for row in listed.json()
    )
    assert (
        member.client.delete(f"/api/auth-states/{ids['another_person']}").status_code
        == 404
    )
    assert (
        member.client.delete(f"/api/auth-states/{ids['another_org']}").status_code
        == 404
    )
    assert (
        member.client.delete(f"/api/auth-states/{ids['organization']}").status_code
        == 204
    )
    assert {row["id"] for row in member.client.get("/api/auth-states").json()} == {
        ids["own"]
    }


def test_organization_and_membership_deletion_cascade_at_their_own_scope(
    new_account: NewAccount,
) -> None:
    owner = new_account()
    member = join(owner, new_account())
    with session_scope() as db:
        organization = store(db, UUID(owner.org_id), None, blob("example.com", "org"))
        personal = store(
            db, UUID(owner.org_id), user_id(member), blob("example.com", "personal")
        )
        db.commit()
        organization_id = organization.id
        personal_id = personal.id

    removed = owner.client.delete(f"/api/orgs/{owner.org_id}/members/{user_id(member)}")
    assert removed.status_code == 204, removed.text
    with session_scope() as db:
        assert db.get(AuthState, personal_id) is None
        assert db.get(AuthState, organization_id) is not None

    name = next(
        org["name"]
        for org in owner.client.get("/api/auth/me").json()["orgs"]
        if org["id"] == owner.org_id
    )
    ended = owner.client.request(
        "DELETE",
        f"/api/orgs/{owner.org_id}",
        json={"name_confirmation": name},
    )
    assert ended.status_code == 204, ended.text
    with session_scope() as db:
        assert db.get(AuthState, organization_id) is None
