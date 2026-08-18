"""The accounts tracer at its seam: HTTP against the app, with a real Postgres.

External behaviour only. The console mailer is the capture point — a test asks
for a Sign-in Code over HTTP and reads the code out of the message that came
back, rather than out of the table that holds its hash.

Two tests do look in a table, and both assert what a table must *not* hold —
no user or Organization after a refused signup, and no code or session token
in the clear. An absence is the one claim no HTTP answer can carry.
"""

import re
from base64 import b64encode
from collections.abc import Iterator
from datetime import timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import func, select
from step_by_step_api import clock
from step_by_step_api.accounts.models import (
    Membership,
    Organization,
    Session,
    SigninCode,
    User,
)
from step_by_step_api.accounts.service import SIGNUP_MODE_VARIABLE
from step_by_step_api.accounts.sessions import SESSION_COOKIE
from step_by_step_api.envelope import KEY_BYTES, master_key
from step_by_step_api.mail import MAILER_VARIABLE, mailer, outbox
from step_by_step_api.main import app
from step_by_step_core.db import session_scope

pytestmark = pytest.mark.integration

DEV_MASTER_KEY = b64encode(bytes(range(KEY_BYTES))).decode()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """The app as uvicorn starts it, on a console mailer of this test's own.

    Both caches are cleared around the test so that the outbox a test reads
    holds its own mail and nobody else's.
    """
    monkeypatch.setenv("STEPBYSTEP_MASTER_KEY", DEV_MASTER_KEY)
    monkeypatch.setenv(MAILER_VARIABLE, "console")
    monkeypatch.delenv(SIGNUP_MODE_VARIABLE, raising=False)
    master_key.cache_clear()
    mailer.cache_clear()
    with TestClient(app) as started:
        yield started
    master_key.cache_clear()
    mailer.cache_clear()


def an_email() -> str:
    """An address no other test in this run uses.

    The compose Postgres is long-lived shared state, so nothing may assume an
    empty `users` table — only that this address is nobody yet.
    """
    return f"ada-{uuid4().hex[:12]}@example.com"


def code_sent_to(address: str) -> str:
    """The 6-digit code from the newest message the console mailer captured."""
    for message in reversed(outbox()):
        if message.to == address:
            digits = re.search(r"\b(\d{6})\b", message.text)
            assert digits is not None, f"no 6-digit code in: {message.text}"
            return digits.group(1)
    raise AssertionError(f"no mail was sent to {address}")


def test_requesting_a_code_emails_six_digits(client: TestClient) -> None:
    email = an_email()

    response = client.post("/api/auth/request-code", json={"email": email})

    assert response.status_code == 202
    assert len(code_sent_to(email)) == 6


def test_requesting_a_code_for_an_unknown_address_looks_the_same(
    client: TestClient,
) -> None:
    """No account-existence oracle: the answer cannot say whether the address
    is anybody, so an attacker cannot enumerate an instance's users."""
    known, unknown = an_email(), an_email()
    client.post("/api/auth/request-code", json={"email": known})
    verify(client, known, code_sent_to(known))

    for_known = client.post("/api/auth/request-code", json={"email": known})
    for_unknown = client.post("/api/auth/request-code", json={"email": unknown})

    assert for_known.status_code == for_unknown.status_code == 202
    assert for_known.content == for_unknown.content == b""


def rows_for(email: str) -> list[object]:
    """The user and Organization rows an address left behind, if any.

    The one look into the tables in this file, and it is here because no HTTP
    answer can show the *absence* of a row: "and no user or Organization rows
    exist afterwards" is a claim about the store itself.
    """
    with session_scope() as db:
        users = (
            db.execute(select(User).where(func.lower(User.email) == email.lower()))
            .scalars()
            .all()
        )
        if not users:
            return []
        organizations = (
            db.execute(
                select(Organization)
                .join(Membership, Membership.org_id == Organization.id)
                .where(Membership.user_id.in_([user.id for user in users]))
            )
            .scalars()
            .all()
        )
        return [*users, *organizations]


def verify(client: TestClient, email: str, code: str) -> Response:
    """Sign in with a code, the way the second step of the screen does."""
    return client.post("/api/auth/verify-code", json={"email": email, "code": code})


def sign_in(client: TestClient, email: str) -> dict[str, object]:
    """The whole two-step flow, which is how every test that needs an account
    gets one: there is no other way to create a user."""
    assert (
        client.post("/api/auth/request-code", json={"email": email}).status_code == 202
    )
    signed_in = verify(client, email, code_sent_to(email))
    assert signed_in.status_code == 200, signed_in.text
    return signed_in.json()


def test_an_unknown_address_becomes_an_account_with_an_organization(
    client: TestClient,
) -> None:
    email = an_email()

    assert sign_in(client, email) == {"created": True}

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    account = me.json()
    assert account["email"] == email
    assert account["display_name"] is None
    assert [(org["name"], org["role"]) for org in account["orgs"]] == [
        (email.split("@")[0], "owner")
    ]


def test_the_session_cookie_is_httponly_and_lax(client: TestClient) -> None:
    """`SameSite=Lax` is the whole CSRF story here, so it is not optional, and
    a script must never be able to read the token. Attribute names and values
    are compared without case, which is how a browser reads them."""
    email = an_email()
    client.post("/api/auth/request-code", json={"email": email})

    signed_in = verify(client, email, code_sent_to(email))

    cookie = signed_in.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_the_session_cookie_is_secure_over_https(client: TestClient) -> None:
    """`Secure` follows the scheme: a plain-HTTP development instance that set
    it would hand out a cookie the browser then refuses to send back."""
    email = an_email()
    client.post("/api/auth/request-code", json={"email": email})
    assert (
        "secure"
        not in verify(client, email, code_sent_to(email)).headers["set-cookie"].lower()
    )

    encrypted = TestClient(client.app, base_url="https://testserver")
    other = an_email()
    encrypted.post("/api/auth/request-code", json={"email": other})
    signed_in = verify(encrypted, other, code_sent_to(other))

    assert "secure" in signed_in.headers["set-cookie"].lower()


def test_the_same_address_in_another_case_is_the_same_account(
    client: TestClient,
) -> None:
    """Email is the sole identity: unique without case, stored as entered."""
    lower = an_email()
    shouted = lower.replace("ada", "Ada").replace("example", "Example")
    sign_in(client, lower)
    first = client.get("/api/auth/me").json()

    assert sign_in(client, shouted) == {"created": False}

    again = client.get("/api/auth/me").json()
    assert again["id"] == first["id"]
    assert again["email"] == lower
    assert len(again["orgs"]) == 1


def test_a_code_works_once(client: TestClient) -> None:
    email = an_email()
    client.post("/api/auth/request-code", json={"email": email})
    code = code_sent_to(email)
    assert verify(client, email, code).status_code == 200

    spent = verify(client, email, code)

    assert spent.status_code == 401
    assert spent.json()["code"] == "bad_code"


def test_a_code_expires_after_ten_minutes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = an_email()
    client.post("/api/auth/request-code", json={"email": email})
    code = code_sent_to(email)
    later = clock.now() + timedelta(minutes=10, seconds=1)
    monkeypatch.setattr(clock, "now", lambda: later)

    stale = verify(client, email, code)

    assert stale.status_code == 401
    assert stale.json()["code"] == "bad_code"


def test_a_wrong_code_is_refused_the_same_way(client: TestClient) -> None:
    """One answer for wrong, expired, spent, and never issued — anything else
    would tell a guesser how close they are."""
    email = an_email()
    client.post("/api/auth/request-code", json={"email": email})
    wrong = "000000" if code_sent_to(email) != "000000" else "111111"

    refused = verify(client, email, wrong)

    assert refused.status_code == 401
    assert refused.json()["code"] == "bad_code"


def test_requesting_a_second_code_retires_the_first(client: TestClient) -> None:
    email = an_email()
    client.post("/api/auth/request-code", json={"email": email})
    first = code_sent_to(email)
    client.post("/api/auth/request-code", json={"email": email})
    assert code_sent_to(email) != first

    assert verify(client, email, first).status_code == 401


def test_an_invite_only_instance_takes_nobody_new(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal waits until verification: asking for a code still answers
    202, because an instance that refused earlier would be saying who has an
    account here."""
    monkeypatch.setenv(SIGNUP_MODE_VARIABLE, "invite_only")
    email = an_email()

    assert (
        client.post("/api/auth/request-code", json={"email": email}).status_code == 202
    )
    closed = verify(client, email, code_sent_to(email))

    assert closed.status_code == 403
    assert closed.json()["code"] == "signup_closed"
    assert client.get("/api/auth/me").status_code == 401
    assert not rows_for(email)


def test_an_existing_account_still_signs_in_on_an_invite_only_instance(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    email = an_email()
    sign_in(client, email)
    monkeypatch.setenv(SIGNUP_MODE_VARIABLE, "invite_only")

    assert sign_in(client, email) == {"created": False}


def test_the_current_account_needs_a_session(client: TestClient) -> None:
    signed_out = client.get("/api/auth/me")

    assert signed_out.status_code == 401
    assert signed_out.json()["code"] == "unauthenticated"


def test_signing_out_kills_the_session_the_browser_still_carries(
    client: TestClient,
) -> None:
    """The cookie the browser kept must stop working, not merely stop being
    sent: a copy of it anywhere is a copy of the session."""
    email = an_email()
    sign_in(client, email)
    cookie = client.cookies[SESSION_COOKIE]

    signed_out = client.post("/api/auth/logout")

    assert signed_out.status_code == 204
    assert signed_out.content == b""
    replayed = client.get(
        "/api/auth/me", headers={"Cookie": f"{SESSION_COOKIE}={cookie}"}
    )
    assert replayed.status_code == 401


def test_a_token_that_matches_no_session_is_not_signed_in(client: TestClient) -> None:
    replayed = client.get(
        "/api/auth/me", headers={"Cookie": f"{SESSION_COOKIE}=not-a-real-token"}
    )

    assert replayed.status_code == 401


def test_the_store_holds_digests_and_never_the_secret(client: TestClient) -> None:
    """The other claim no HTTP answer can show: what the tables must not hold.

    A leaked backup, a replicated table, or a query in a log must hand nobody
    a working code or a working session token.
    """
    email = an_email()
    client.post("/api/auth/request-code", json={"email": email})
    code = code_sent_to(email)

    with session_scope() as db:
        stored = db.execute(
            select(SigninCode).where(SigninCode.email == email.lower())
        ).scalar_one()
        assert code not in stored.code_hash
        assert stored.code_hash == sha256(code.encode()).hexdigest()

    verify(client, email, code)
    token = client.cookies[SESSION_COOKIE]

    # 128 bits is the floor the design sets; urlsafe base64 carries 6 bits a
    # character, so anything shorter than 22 characters is under it.
    assert len(token) >= 22
    with session_scope() as db:
        held = db.execute(select(Session.token_hash)).scalars().all()
        assert token not in held
        assert sha256(token.encode()).hexdigest() in held


def test_a_display_name_is_the_one_thing_an_account_can_change(
    client: TestClient,
) -> None:
    email = an_email()
    sign_in(client, email)

    named = client.patch("/api/account", json={"display_name": "Ada Lovelace"})

    assert named.status_code == 200
    assert named.json()["display_name"] == "Ada Lovelace"
    assert named.json()["email"] == email
    assert client.get("/api/auth/me").json()["display_name"] == "Ada Lovelace"


def test_changing_a_display_name_needs_a_session(client: TestClient) -> None:
    assert (
        client.patch("/api/account", json={"display_name": "nobody"}).status_code == 401
    )
