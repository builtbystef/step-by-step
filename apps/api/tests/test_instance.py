import pytest
from fastapi.testclient import TestClient
from step_by_step_api.accounts.service import (
    DEFAULT_TIMEZONE_VARIABLE,
    SIGNUP_MODE_VARIABLE,
    DefaultTimezoneError,
    SignupModeError,
)
from step_by_step_api.main import app

client = TestClient(app)


def test_signup_mode_defaults_to_open(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SIGNUP_MODE_VARIABLE, raising=False)
    monkeypatch.delenv(DEFAULT_TIMEZONE_VARIABLE, raising=False)

    response = client.get("/api/instance")

    assert response.status_code == 200
    assert response.json() == {"signup_mode": "open", "default_timezone": "UTC"}


def test_signup_mode_reflects_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SIGNUP_MODE_VARIABLE, "invite_only")
    monkeypatch.delenv(DEFAULT_TIMEZONE_VARIABLE, raising=False)

    response = client.get("/api/instance")

    assert response.status_code == 200
    assert response.json() == {
        "signup_mode": "invite_only",
        "default_timezone": "UTC",
    }


def test_the_spec_spelling_with_a_hyphen_is_the_same_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(SIGNUP_MODE_VARIABLE, "invite-only")
    monkeypatch.delenv(DEFAULT_TIMEZONE_VARIABLE, raising=False)

    assert client.get("/api/instance").json() == {
        "signup_mode": "invite_only",
        "default_timezone": "UTC",
    }


def test_an_unknown_signup_mode_names_the_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(SIGNUP_MODE_VARIABLE, "nobody")

    with pytest.raises(SignupModeError, match=SIGNUP_MODE_VARIABLE):
        client.get("/api/instance")


def test_default_timezone_comes_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(SIGNUP_MODE_VARIABLE, raising=False)
    monkeypatch.setenv(DEFAULT_TIMEZONE_VARIABLE, "Europe/Belgrade")

    assert client.get("/api/instance").json()["default_timezone"] == "Europe/Belgrade"


def test_an_unknown_default_timezone_names_the_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(DEFAULT_TIMEZONE_VARIABLE, "Mars/Olympus")

    with pytest.raises(DefaultTimezoneError, match=DEFAULT_TIMEZONE_VARIABLE):
        client.get("/api/instance")
