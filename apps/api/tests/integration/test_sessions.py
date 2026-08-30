from collections.abc import Callable
from datetime import datetime, timedelta

import pytest
from conftest import Account, code_sent_to
from fastapi.testclient import TestClient
from step_by_step_api import clock
from step_by_step_api.accounts import sessions
from step_by_step_api.accounts.models import Session
from step_by_step_api.accounts.sessions import SESSION_COOKIE
from step_by_step_api.main import app
from step_by_step_core.db import session_scope

pytestmark = pytest.mark.integration

NewAccount = Callable[[], Account]
Travel = Callable[[timedelta], None]

DAY = timedelta(days=1)


@pytest.fixture
def travel(monkeypatch: pytest.MonkeyPatch) -> Travel:
    started = clock.now()

    def forward(elapsed: timedelta) -> None:
        monkeypatch.setattr(clock, "now", lambda: started + elapsed)

    return forward


def me(account: Account) -> int:
    return account.client.get("/api/auth/me").status_code


def stored_session(account: Account) -> Session | None:
    with session_scope() as db:
        return db.get(
            Session, sessions.token_digest(account.client.cookies[SESSION_COOKIE])
        )


def last_seen(account: Account) -> datetime:
    stored = stored_session(account)
    assert stored is not None
    return stored.last_seen_at


def another_device(account: Account) -> TestClient:
    browser = TestClient(app)
    asked = browser.post("/api/auth/request-code", json={"email": account.email})
    assert asked.status_code == 202
    signed_in = browser.post(
        "/api/auth/verify-code",
        json={"email": account.email, "code": code_sent_to(account.email)},
    )
    assert signed_in.status_code == 200, signed_in.text
    return browser


def test_a_session_used_before_it_runs_out_gets_another_thirty_days(
    new_account: NewAccount, travel: Travel
) -> None:
    account = new_account()

    travel(29 * DAY)
    assert me(account) == 200

    travel(50 * DAY)
    assert me(account) == 200


def test_a_session_nobody_used_for_thirty_days_is_over(
    new_account: NewAccount, travel: Travel
) -> None:
    account = new_account()

    travel(31 * DAY)

    refused = account.client.get("/api/auth/me")
    assert refused.status_code == 401
    assert refused.json()["code"] == "unauthenticated"
    assert stored_session(account) is None


def test_a_busy_session_is_written_at_most_once_an_hour(
    new_account: NewAccount, travel: Travel
) -> None:
    account = new_account()
    opened = last_seen(account)

    travel(timedelta(minutes=1))
    assert me(account) == 200
    assert last_seen(account) == opened

    travel(timedelta(minutes=61))
    assert me(account) == 200
    assert last_seen(account) > opened


def test_signing_out_everywhere_ends_every_session_this_person_has(
    new_account: NewAccount,
) -> None:
    account = new_account()
    phone = another_device(account)
    stranger = new_account()
    here = account.client.cookies[SESSION_COOKIE]

    everywhere = account.client.post("/api/auth/logout-all")

    assert everywhere.status_code == 204, everywhere.text
    assert everywhere.content == b""
    assert phone.get("/api/auth/me").status_code == 401
    replayed = account.client.get(
        "/api/auth/me", headers={"Cookie": f"{SESSION_COOKIE}={here}"}
    )
    assert replayed.status_code == 401
    assert me(stranger) == 200


def test_signing_out_everywhere_needs_a_session(client: TestClient) -> None:
    assert client.post("/api/auth/logout-all").status_code == 401


def test_a_sliding_session_hands_the_browser_a_fresh_cookie(
    new_account: NewAccount, travel: Travel
) -> None:
    account = new_account()

    travel(20 * DAY)
    answered = account.client.get("/api/auth/me")

    assert answered.status_code == 200
    handed = answered.headers.get("set-cookie", "")
    assert SESSION_COOKIE in handed
    assert f"Max-Age={int(sessions.SESSION_LIFETIME.total_seconds())}" in handed
