"""The integration tier's fixtures.

Every test here runs against the real Postgres from the compose stack. That
stack is long-lived shared state, so the tier never assumes a fresh one: each
run creates a database of its own, migrates it, and drops it afterwards.

The account fixtures are scaffolding for the domain tests: signing in is the
only way to create a user, and every domain route acts inside an Organization.
`tests/integration/test_accounts.py` keeps its own helpers, because there the
sign-in flow is the subject rather than the setup.
"""

import os
import re
from base64 import b64encode
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from step_by_step_api.accounts.service import SIGNUP_MODE_VARIABLE
from step_by_step_api.db import get_engine
from step_by_step_api.envelope import KEY_BYTES, master_key
from step_by_step_api.mail import MAILER_VARIABLE, mailer, outbox
from step_by_step_api.main import app

ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"

DEV_MASTER_KEY = b64encode(bytes(range(KEY_BYTES))).decode()


@pytest.fixture
def migration_runner() -> Config:
    """The migration runner, configured exactly as the command line configures it."""
    return Config(str(ALEMBIC_INI))


@pytest.fixture(scope="session")
def run_database_url() -> Iterator[str]:
    """A database this run owns, on the shared compose Postgres."""
    admin_url = make_url(os.environ["DATABASE_URL"])
    name = f"stepbystep_test_{uuid4().hex[:12]}"
    admin_engine = create_engine(
        admin_url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        yield admin_url.set(database=name).render_as_string(hide_password=False)
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated_database(run_database_url: str) -> Iterator[None]:
    """Point the app's engine at this run's database and migrate it to head."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", run_database_url)
        get_engine.cache_clear()
        command.upgrade(Config(str(ALEMBIC_INI)), "head")
        yield
        get_engine().dispose()
    get_engine.cache_clear()


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


@dataclass(frozen=True, slots=True)
class Account:
    """A signed-in account, on a client that already acts in its Organization."""

    client: TestClient
    email: str
    org_id: str


@pytest.fixture
def new_account() -> Callable[[], Account]:
    """Sign a brand-new account in, each on a browser of its own.

    Domain tests need accounts the way they need a database — as scaffolding,
    not as the subject — and every account here owns the Organization its
    signup created, so two calls are two tenants. The client carries the
    `X-Organization` header from then on, which is what the frontend's fetch
    wrapper does.
    """

    def make() -> Account:
        email = f"ada-{uuid4().hex[:12]}@example.com"
        browser = TestClient(app)
        assert (
            browser.post("/api/auth/request-code", json={"email": email}).status_code
            == 202
        )
        code = code_sent_to(email)
        assert (
            browser.post(
                "/api/auth/verify-code", json={"email": email, "code": code}
            ).status_code
            == 200
        )
        org_id = browser.get("/api/auth/me").json()["orgs"][0]["id"]
        browser.headers["X-Organization"] = org_id
        return Account(client=browser, email=email, org_id=org_id)

    return make


def code_sent_to(address: str) -> str:
    """The 6-digit Sign-in Code from the newest message the mailer captured."""
    for message in reversed(outbox()):
        if message.to == address:
            digits = re.search(r"\b(\d{6})\b", message.text)
            assert digits is not None, f"no 6-digit code in: {message.text}"
            return digits.group(1)
    raise AssertionError(f"no mail was sent to {address}")


def join(owner: Account, invitee: Account, role: str = "member") -> Account:
    """The invitee, now in the owner's Organization with that role.

    An Invitation is the only way in — there is no instance administrator and
    no other route that makes a Membership — so every test that needs a second
    person in an Organization builds them here.
    """
    invited = owner.client.post(
        f"/api/orgs/{owner.org_id}/invitations",
        json={"email": invitee.email, "role": role},
    )
    assert invited.status_code == 201, invited.text
    accepted = invitee.client.post(f"/api/invitations/{invited.json()['id']}/accept")
    assert accepted.status_code == 204, accepted.text
    return Account(client=invitee.client, email=invitee.email, org_id=owner.org_id)
