"""Sessions at their seam: how long one lives, and how they all end at once.

HTTP against the app, with a real Postgres, and the clock moved rather than
waited on — a session that expires after 30 idle days is otherwise a test that
takes a month.
"""

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
    """Move every clock the application reads, forward from this moment.

    One place, because a session's whole life is measured against `clock.now()`
    — and a test that waited the 30 idle days out would never run.
    """
    started = clock.now()

    def forward(elapsed: timedelta) -> None:
        monkeypatch.setattr(clock, "now", lambda: started + elapsed)

    return forward


def me(account: Account) -> int:
    """What the account's own browser gets when it asks who it is."""
    return account.client.get("/api/auth/me").status_code


def stored_session(account: Account) -> Session | None:
    """The row behind this browser's cookie, if the store still holds one.

    The one look into a table in this file, and both claims it carries are ones
    no answer can: that an expired session is *gone* rather than merely refused,
    and how often `last_seen_at` is written — the two requests whose writes are
    being counted both answer 200 either way.
    """
    with session_scope() as db:
        return db.get(
            Session, sessions.token_digest(account.client.cookies[SESSION_COOKIE])
        )


def last_seen(account: Account) -> datetime:
    """When the store thinks this session was last used."""
    stored = stored_session(account)
    assert stored is not None
    return stored.last_seen_at


def another_device(account: Account) -> TestClient:
    """The same person signing in again, on a second browser of their own."""
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
    """Sliding, not fixed: 29 idle days is still signed in, and being used is
    what buys the next thirty — so somebody who visits weekly never signs in
    again."""
    account = new_account()

    travel(29 * DAY)
    assert me(account) == 200

    travel(50 * DAY)
    assert me(account) == 200


def test_a_session_nobody_used_for_thirty_days_is_over(
    new_account: NewAccount, travel: Travel
) -> None:
    """Silence expires a session, and the refusal is the same `unauthenticated`
    every other way of not being signed in gets."""
    account = new_account()

    travel(31 * DAY)

    refused = account.client.get("/api/auth/me")
    assert refused.status_code == 401
    assert refused.json()["code"] == "unauthenticated"
    # And it stays over: the row is gone, so no later request can find it, and
    # a table nobody sweeps does not fill up with sessions nobody can use.
    assert stored_session(account) is None


def test_a_busy_session_is_written_at_most_once_an_hour(
    new_account: NewAccount, travel: Travel
) -> None:
    """A screen full of requests must not be a screen full of writes: the
    column measures silence in days, so an hour of resolution is plenty."""
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
    """What the action is for: a phone left somewhere, signed out from a
    machine the person still has. Nobody else's sessions move."""
    account = new_account()
    phone = another_device(account)
    stranger = new_account()
    here = account.client.cookies[SESSION_COOKIE]

    everywhere = account.client.post("/api/auth/logout-all")

    assert everywhere.status_code == 204, everywhere.text
    assert everywhere.content == b""
    assert phone.get("/api/auth/me").status_code == 401
    # The token this browser was carrying, and not merely the cookie it stopped
    # sending: a copy of it anywhere is a copy of the session.
    replayed = account.client.get(
        "/api/auth/me", headers={"Cookie": f"{SESSION_COOKIE}={here}"}
    )
    assert replayed.status_code == 401
    assert me(stranger) == 200


def test_signing_out_everywhere_needs_a_session(client: TestClient) -> None:
    """Whose sessions would it end? There is nobody to name, so it refuses."""
    assert client.post("/api/auth/logout-all").status_code == 401


def test_a_sliding_session_hands_the_browser_a_fresh_cookie(
    new_account: NewAccount, travel: Travel
) -> None:
    """The cookie has to slide with the row it points at.

    It is written with a 30-day lifetime of its own, so a browser told nothing
    more would throw it away 30 days after signing in — and the session it
    still had on the server would be one nobody could reach. Extending in the
    store alone extends nothing anyone can use.
    """
    account = new_account()

    travel(20 * DAY)
    answered = account.client.get("/api/auth/me")

    assert answered.status_code == 200
    handed = answered.headers.get("set-cookie", "")
    assert SESSION_COOKIE in handed
    assert f"Max-Age={int(sessions.SESSION_LIFETIME.total_seconds())}" in handed
