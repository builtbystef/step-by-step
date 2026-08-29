"""rotate-master-key, against real Postgres.

The envelope module already proves rewrap on a single record. This is the
command that walks every sealed row — Secrets, Auth States, and Personal
Overrides of both — so a leaked master key is recoverable without dumping
the database.

The session-scoped test database accumulates vault rows sealed under
whichever master key each test happened to have. Rotation walks every row,
so these tests empty the vault first and seed a known mixed set.
"""

from base64 import b64encode
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from uuid import UUID

import pytest
from conftest import Account
from fastapi.testclient import TestClient
from nacl.exceptions import CryptoError
from sqlalchemy import delete, select
from step_by_step_api.auth_states.models import AuthState
from step_by_step_api.auth_states.store import store
from step_by_step_api.cli import main
from step_by_step_api.envelope import (
    KEY_BYTES,
    NEW_MASTER_KEY_VARIABLE,
    Sealed,
    master_key,
    open_sealed,
    rewrap,
)
from step_by_step_api.secrets.models import Secret, SecretOverride
from step_by_step_core.db import session_scope
from test_auth_states import blob, user_id

pytestmark = pytest.mark.integration
NewAccount = Callable[[], Account]

CURRENT = bytes(range(KEY_BYTES))
NEW = bytes(range(KEY_BYTES, KEY_BYTES * 2))
NEW_B64 = b64encode(NEW).decode()


@dataclass(frozen=True, slots=True)
class VaultRow:
    """One sealed row as rotation found it, with the plaintext it must keep."""

    kind: str
    id: UUID
    ciphertext: bytes
    plaintext: bytes


def empty_the_vault() -> None:
    with session_scope() as db:
        db.execute(delete(SecretOverride))
        db.execute(delete(Secret))
        db.execute(delete(AuthState))
        db.commit()


@pytest.fixture
def mixed_vault(
    client: TestClient, new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> Iterator[list[VaultRow]]:
    """Four sealed kinds under the current key, and the new key in the environment."""
    empty_the_vault()
    monkeypatch.setenv(NEW_MASTER_KEY_VARIABLE, NEW_B64)
    owner = new_account()
    secret = owner.client.post(
        "/api/secrets", json={"name": "Portal password", "value": "org-secret"}
    )
    assert secret.status_code == 201, secret.text
    overridden = owner.client.put(
        f"/api/secrets/{secret.json()['id']}/override",
        json={"value": "personal-secret"},
    )
    assert overridden.status_code == 204, overridden.text
    with session_scope() as db:
        store(db, UUID(owner.org_id), None, blob("rotate.example", "org-cookie"))
        store(
            db,
            UUID(owner.org_id),
            user_id(owner),
            blob("personal.example", "personal-cookie"),
        )
        db.commit()
    yield snapshot_under(CURRENT)
    empty_the_vault()
    master_key.cache_clear()


def snapshot_under(key: bytes) -> list[VaultRow]:
    items: list[VaultRow] = []
    with session_scope() as db:
        for row in db.scalars(select(Secret)).all():
            items.append(
                VaultRow(
                    "secret",
                    row.id,
                    row.sealed_value,
                    open_sealed(Sealed(row.sealed_value, row.sealed_data_key), key),
                )
            )
        for row in db.scalars(select(SecretOverride)).all():
            items.append(
                VaultRow(
                    "secret_override",
                    row.id,
                    row.sealed_value,
                    open_sealed(Sealed(row.sealed_value, row.sealed_data_key), key),
                )
            )
        for row in db.scalars(select(AuthState)).all():
            kind = "auth_state_org" if row.user_id is None else "auth_state_personal"
            items.append(
                VaultRow(
                    kind,
                    row.id,
                    row.sealed_blob,
                    open_sealed(Sealed(row.sealed_blob, row.sealed_data_key), key),
                )
            )
    return items


def assert_opens_only_under(before: list[VaultRow], key: bytes) -> None:
    with session_scope() as db:
        secrets = {row.id: row for row in db.scalars(select(Secret)).all()}
        overrides = {row.id: row for row in db.scalars(select(SecretOverride)).all()}
        states = {row.id: row for row in db.scalars(select(AuthState)).all()}
    other = CURRENT if key == NEW else NEW
    for item in before:
        if item.kind == "secret":
            value = secrets[item.id].sealed_value
            data_key = secrets[item.id].sealed_data_key
        elif item.kind == "secret_override":
            value, data_key = (
                overrides[item.id].sealed_value,
                overrides[item.id].sealed_data_key,
            )
        else:
            value, data_key = (
                states[item.id].sealed_blob,
                states[item.id].sealed_data_key,
            )
        assert value == item.ciphertext
        assert open_sealed(Sealed(value, data_key), key) == item.plaintext
        with pytest.raises(CryptoError):
            open_sealed(Sealed(value, data_key), other)


def test_rotation_moves_every_kind_of_sealed_row(
    mixed_vault: list[VaultRow], capsys: pytest.CaptureFixture[str]
) -> None:
    kinds = {item.kind for item in mixed_vault}
    assert kinds == {
        "secret",
        "secret_override",
        "auth_state_org",
        "auth_state_personal",
    }

    main()
    printed = capsys.readouterr().out

    assert f"re-wrapped: {len(mixed_vault)}" in printed
    assert "already-rotated: 0" in printed
    assert_opens_only_under(mixed_vault, NEW)


def test_a_second_pass_rewrites_nothing(
    mixed_vault: list[VaultRow], capsys: pytest.CaptureFixture[str]
) -> None:
    main()
    capsys.readouterr()
    main()
    printed = capsys.readouterr().out

    assert "re-wrapped: 0" in printed
    assert f"already-rotated: {len(mixed_vault)}" in printed
    assert_opens_only_under(mixed_vault, NEW)


def test_an_interrupted_pass_completes_on_re_run(
    mixed_vault: list[VaultRow], capsys: pytest.CaptureFixture[str]
) -> None:
    moved = [item for item in mixed_vault if item.kind in {"secret", "auth_state_org"}]
    with session_scope() as db:
        for item in moved:
            model = Secret if item.kind == "secret" else AuthState
            row = db.get_one(model, item.id)
            rotated = rewrap(row.sealed_data_key, CURRENT, NEW)
            assert rotated is not None
            row.sealed_data_key = rotated
        db.commit()

    main()
    printed = capsys.readouterr().out

    remaining = len(mixed_vault) - len(moved)
    assert f"re-wrapped: {remaining}" in printed
    assert f"already-rotated: {len(moved)}" in printed
    assert_opens_only_under(mixed_vault, NEW)
