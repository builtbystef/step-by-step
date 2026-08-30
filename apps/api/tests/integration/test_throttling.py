from collections.abc import Callable
from datetime import timedelta
from uuid import uuid4

import pytest
from conftest import code_sent_to
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from step_by_step_api import clock
from step_by_step_api.accounts.models import CodeIssuance
from step_by_step_core.db import session_scope

pytestmark = pytest.mark.integration

Travel = Callable[[timedelta], None]

ATTEMPT_CAP = 5

ISSUANCE_LIMIT = 5

ISSUANCE_WINDOW = timedelta(hours=1)


@pytest.fixture
def travel(monkeypatch: pytest.MonkeyPatch) -> Travel:
    started = clock.now()

    def forward(elapsed: timedelta) -> None:
        monkeypatch.setattr(clock, "now", lambda: started + elapsed)

    return forward


def an_email() -> str:
    return f"ada-{uuid4().hex[:12]}@example.com"


def request_code(client: TestClient, email: str) -> Response:
    return client.post("/api/auth/request-code", json={"email": email})


def verify(client: TestClient, email: str, code: str) -> Response:
    return client.post("/api/auth/verify-code", json={"email": email, "code": code})


def a_wrong_code(right: str) -> str:
    return "000000" if right != "000000" else "111111"


def guess_wrong(client: TestClient, email: str, times: int) -> None:
    right = code_sent_to(email)
    for _ in range(times):
        refused = verify(client, email, a_wrong_code(right))
        assert refused.status_code == 401, refused.text
        assert refused.json()["code"] == "bad_code"


def spend_the_issuance(client: TestClient, email: str) -> None:
    for _ in range(ISSUANCE_LIMIT):
        asked = request_code(client, email)
        assert asked.status_code == 202, asked.text


def test_a_code_dies_after_five_wrong_guesses(client: TestClient) -> None:
    email = an_email()
    request_code(client, email)
    right = code_sent_to(email)

    guess_wrong(client, email, ATTEMPT_CAP)

    exhausted = verify(client, email, right)
    assert exhausted.status_code == 429
    assert exhausted.json()["code"] == "code_exhausted"


def test_a_fresh_code_recovers_an_exhausted_address(client: TestClient) -> None:
    email = an_email()
    request_code(client, email)
    guess_wrong(client, email, ATTEMPT_CAP)

    assert request_code(client, email).status_code == 202

    signed_in = verify(client, email, code_sent_to(email))
    assert signed_in.status_code == 200, signed_in.text


def test_guessing_at_one_address_leaves_another_alone(client: TestClient) -> None:
    guessed_at, untouched = an_email(), an_email()
    request_code(client, guessed_at)
    request_code(client, untouched)

    guess_wrong(client, guessed_at, ATTEMPT_CAP)

    assert verify(client, guessed_at, code_sent_to(guessed_at)).status_code == 429
    signed_in = verify(client, untouched, code_sent_to(untouched))
    assert signed_in.status_code == 200, signed_in.text


def test_an_address_is_sent_five_codes_an_hour_and_no_more(
    client: TestClient,
) -> None:
    email = an_email()
    spend_the_issuance(client, email)
    sent = code_sent_to(email)

    sprayed = request_code(client, email)

    assert sprayed.status_code == 429
    assert sprayed.json()["code"] == "rate_limited"
    assert code_sent_to(email) == sent, "a refused request still mailed a code"


def test_the_window_passing_lets_the_address_be_written_to_again(
    client: TestClient, travel: Travel
) -> None:
    email = an_email()
    spend_the_issuance(client, email)
    assert request_code(client, email).status_code == 429

    travel(ISSUANCE_WINDOW + timedelta(minutes=1))

    assert request_code(client, email).status_code == 202
    signed_in = verify(client, email, code_sent_to(email))
    assert signed_in.status_code == 200, signed_in.text


def test_one_address_being_sprayed_does_not_silence_another(
    client: TestClient,
) -> None:
    sprayed, untouched = an_email(), an_email()
    spend_the_issuance(client, sprayed)
    assert request_code(client, sprayed).status_code == 429

    assert request_code(client, untouched).status_code == 202


def issuance_row(email: str) -> CodeIssuance | None:
    with session_scope() as db:
        return db.execute(
            select(CodeIssuance).where(CodeIssuance.email == email.lower())
        ).scalar_one_or_none()


def test_an_issuance_row_is_gone_once_its_window_has_passed(
    client: TestClient, travel: Travel
) -> None:
    abandoned, other = an_email(), an_email()
    spend_the_issuance(client, abandoned)
    assert issuance_row(abandoned) is not None

    travel(ISSUANCE_WINDOW + timedelta(minutes=1))
    assert request_code(client, other).status_code == 202

    assert issuance_row(abandoned) is None


def test_sweeping_a_closed_window_does_not_lift_an_open_one(
    client: TestClient, travel: Travel
) -> None:
    capped, other = an_email(), an_email()
    spend_the_issuance(client, capped)

    assert request_code(client, other).status_code == 202
    assert request_code(client, capped).status_code == 429
    assert issuance_row(capped) is not None

    travel(ISSUANCE_WINDOW + timedelta(minutes=1))
    assert request_code(client, other).status_code == 202
    assert issuance_row(capped) is None
    assert request_code(client, capped).status_code == 202
