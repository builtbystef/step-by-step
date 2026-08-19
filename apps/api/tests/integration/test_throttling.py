"""Sign-in Code throttling at its seam: HTTP against the app, real Postgres.

A six-digit code is guessable in a million tries and sprayable in as many
requests, so two caps stand behind it: a code dies after five wrong guesses,
and one address is sent at most five codes an hour. The hour is moved rather
than waited out — the clock is the one the application reads.
"""

from collections.abc import Callable
from datetime import timedelta
from uuid import uuid4

import pytest
from conftest import code_sent_to
from fastapi.testclient import TestClient
from httpx import Response
from step_by_step_api import clock

pytestmark = pytest.mark.integration

Travel = Callable[[timedelta], None]

ATTEMPT_CAP = 5
"""Wrong guesses a code survives, from the spec: the sixth attempt is refused."""

ISSUANCE_LIMIT = 5
"""Codes one address is sent per window, from the spec: the sixth is refused."""

ISSUANCE_WINDOW = timedelta(hours=1)
"""The window those five are counted in."""


@pytest.fixture
def travel(monkeypatch: pytest.MonkeyPatch) -> Travel:
    """Move every clock the application reads, forward from this moment.

    The issuance window is an hour, and a test that waited it out would be an
    hour long; `clock` is the one place the time enters, so moving it is the
    whole of the travel.
    """
    started = clock.now()

    def forward(elapsed: timedelta) -> None:
        monkeypatch.setattr(clock, "now", lambda: started + elapsed)

    return forward


def an_email() -> str:
    """An address no other test in this run uses.

    Both caps are per address, so an address of one test's own is what keeps
    one test's guessing out of another's count.
    """
    return f"ada-{uuid4().hex[:12]}@example.com"


def request_code(client: TestClient, email: str) -> Response:
    """Step one of the sign-in screen: ask for a code."""
    return client.post("/api/auth/request-code", json={"email": email})


def verify(client: TestClient, email: str, code: str) -> Response:
    """Step two: enter a code, right or wrong."""
    return client.post("/api/auth/verify-code", json={"email": email, "code": code})


def a_wrong_code(right: str) -> str:
    """Six digits that are not the ones that were sent."""
    return "000000" if right != "000000" else "111111"


def guess_wrong(client: TestClient, email: str, times: int) -> None:
    """Spend `times` guesses against the live code, each of them refused."""
    right = code_sent_to(email)
    for _ in range(times):
        refused = verify(client, email, a_wrong_code(right))
        assert refused.status_code == 401, refused.text
        assert refused.json()["code"] == "bad_code"


def spend_the_issuance(client: TestClient, email: str) -> None:
    """Ask for every code the address is allowed in this window."""
    for _ in range(ISSUANCE_LIMIT):
        asked = request_code(client, email)
        assert asked.status_code == 202, asked.text


def test_a_code_dies_after_five_wrong_guesses(client: TestClient) -> None:
    """The cap is what makes six digits enough: a guesser gets five tries at
    one code, and the right code afterwards is worth nothing."""
    email = an_email()
    request_code(client, email)
    right = code_sent_to(email)

    guess_wrong(client, email, ATTEMPT_CAP)

    exhausted = verify(client, email, right)
    assert exhausted.status_code == 429
    assert exhausted.json()["code"] == "code_exhausted"


def test_a_fresh_code_recovers_an_exhausted_address(client: TestClient) -> None:
    """The cap kills a code, never an address: asking for another one is the
    way back, and it is the person who owns the mailbox who can ask."""
    email = an_email()
    request_code(client, email)
    guess_wrong(client, email, ATTEMPT_CAP)

    assert request_code(client, email).status_code == 202

    signed_in = verify(client, email, code_sent_to(email))
    assert signed_in.status_code == 200, signed_in.text


def test_guessing_at_one_address_leaves_another_alone(client: TestClient) -> None:
    """The count belongs to one code and one address. Otherwise guessing at a
    stranger's code would lock everyone else's out with it."""
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
    """The one exception to request-code's always-202: an address somebody is
    spraying stops receiving mail, and the answer says why."""
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
    """A limit that never lifted would be an address locked out for good by
    anybody who knew it."""
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
    """The count is the address's own, or spraying one address would stop the
    whole instance from signing anybody in."""
    sprayed, untouched = an_email(), an_email()
    spend_the_issuance(client, sprayed)
    assert request_code(client, sprayed).status_code == 429

    assert request_code(client, untouched).status_code == 202
