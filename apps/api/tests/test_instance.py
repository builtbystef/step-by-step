"""What an unauthenticated visitor may learn about this instance.

Exactly one fact: whether verifying a Sign-in Code for an unknown address
creates an account. The sign-in screen shows different copy for the two, and
it must not hardcode either. Nothing here needs a service.
"""

import pytest
from fastapi.testclient import TestClient
from step_by_step_api.accounts.service import SIGNUP_MODE_VARIABLE, SignupModeError
from step_by_step_api.main import app

client = TestClient(app)


def test_signup_mode_defaults_to_open(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SIGNUP_MODE_VARIABLE, raising=False)

    response = client.get("/api/instance")

    assert response.status_code == 200
    assert response.json() == {"signup_mode": "open"}


def test_signup_mode_reflects_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SIGNUP_MODE_VARIABLE, "invite_only")

    response = client.get("/api/instance")

    assert response.status_code == 200
    assert response.json() == {"signup_mode": "invite_only"}


def test_the_spec_spelling_with_a_hyphen_is_the_same_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`invite-only` is how the spec's prose writes it, and a self-hoster
    copying that word must not meet a boot failure."""
    monkeypatch.setenv(SIGNUP_MODE_VARIABLE, "invite-only")

    assert client.get("/api/instance").json() == {"signup_mode": "invite_only"}


def test_an_unknown_signup_mode_names_the_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(SIGNUP_MODE_VARIABLE, "nobody")

    with pytest.raises(SignupModeError, match=SIGNUP_MODE_VARIABLE):
        client.get("/api/instance")
