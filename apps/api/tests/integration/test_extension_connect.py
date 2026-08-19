"""The connect code: the second way an extension reaches an instance.

The first way is the handshake on the app's connect page, which needs the
extension to be allowed to inject there. When that does not happen, the app
shows a code and the extension spends it here. A spent code proves what the
handshake proves and nothing more: the origin is a live instance, and somebody
signed into it authorized this pairing.
"""

from collections.abc import Callable
from datetime import timedelta

import pytest
from conftest import Account
from fastapi.testclient import TestClient
from sqlalchemy import select
from step_by_step_api import clock
from step_by_step_api.extension.models import ExtensionConnectCode
from step_by_step_core.db import session_scope

pytestmark = pytest.mark.integration

NewAccount = Callable[[], Account]


def test_a_signed_in_user_takes_a_code_and_the_extension_spends_it(
    client: TestClient, new_account: NewAccount
) -> None:
    account = new_account()

    minted = account.client.post("/api/extension/connect-codes")
    assert minted.status_code == 201
    code = minted.json()["code"]

    # The extension has no session: the code is the whole of what it presents.
    assert client.post("/api/extension/connect", json={"code": code}).status_code == 200


def test_a_code_is_single_use(client: TestClient, new_account: NewAccount) -> None:
    account = new_account()
    code = account.client.post("/api/extension/connect-codes").json()["code"]

    assert client.post("/api/extension/connect", json={"code": code}).status_code == 200

    spent = client.post("/api/extension/connect", json={"code": code})
    assert spent.status_code == 401
    assert spent.json()["code"] == "bad_code"


def test_a_code_runs_out_after_ten_minutes(
    client: TestClient, new_account: NewAccount, monkeypatch: pytest.MonkeyPatch
) -> None:
    account = new_account()
    minted = account.client.post("/api/extension/connect-codes").json()
    later = clock.now() + timedelta(minutes=11)
    monkeypatch.setattr(clock, "now", lambda: later)

    refused = client.post("/api/extension/connect", json={"code": minted["code"]})

    assert refused.status_code == 401
    assert refused.json()["code"] == "bad_code"


def test_a_code_that_was_never_issued_is_refused_the_same_way(
    client: TestClient,
) -> None:
    refused = client.post("/api/extension/connect", json={"code": "ABCD-EFGH-JKLM"})

    assert refused.status_code == 401
    assert refused.json()["code"] == "bad_code"


def test_a_code_is_read_as_it_was_copied(
    client: TestClient, new_account: NewAccount
) -> None:
    """Whatever the paste carried: the case it was shown in, its dashes, and
    the spaces a selection drags along."""
    account = new_account()
    code = account.client.post("/api/extension/connect-codes").json()["code"]
    pasted = f"  {code.lower().replace('-', ' ')}  "

    assert (
        client.post("/api/extension/connect", json={"code": pasted}).status_code == 200
    )


def test_taking_a_code_needs_a_session(client: TestClient) -> None:
    assert client.post("/api/extension/connect-codes").status_code == 401


def test_the_code_is_never_held_in_the_clear(
    client: TestClient, new_account: NewAccount
) -> None:
    """An absence no HTTP answer can carry, so this one test reads the table."""
    account = new_account()
    code = account.client.post("/api/extension/connect-codes").json()["code"]

    with session_scope() as db:
        held = db.execute(select(ExtensionConnectCode.code_hash)).scalars().all()

    assert code not in held
    assert all(len(digest) == 64 for digest in held)
