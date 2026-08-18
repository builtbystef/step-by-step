"""The master-key boot gate.

Losing the master key makes every stored value unrecoverable, and a backend
that starts without a usable one would serve traffic until the first secret and
then fail — with the vault half-written and the operator none the wiser. So the
key is proven at startup: a bad key is a boot failure, never a first-use one.

The app is started through the test client's lifespan, which is the same
startup uvicorn runs; nothing here needs a service.
"""

from base64 import b64encode
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from step_by_step_api.envelope import KEY_BYTES, MasterKeyError, master_key
from step_by_step_api.mail import MailerConfigurationError, mailer
from step_by_step_api.main import app

VALID = b64encode(bytes(range(KEY_BYTES))).decode()


@pytest.fixture(autouse=True)
def unconfigured_boot() -> Iterator[None]:
    """No test here may inherit — or leave behind — what a boot caches."""
    master_key.cache_clear()
    mailer.cache_clear()
    yield
    master_key.cache_clear()
    mailer.cache_clear()


def test_the_backend_starts_with_a_valid_master_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STEPBYSTEP_MASTER_KEY", VALID)

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200


def test_the_backend_refuses_to_start_without_a_master_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("STEPBYSTEP_MASTER_KEY", raising=False)

    with pytest.raises(MasterKeyError, match="not set"), TestClient(app):
        pass


def test_the_backend_refuses_to_start_on_a_key_that_is_not_base64(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STEPBYSTEP_MASTER_KEY", "not base64 at all!!")

    with pytest.raises(MasterKeyError, match="base64"), TestClient(app):
        pass


def test_the_backend_refuses_to_start_on_a_key_of_the_wrong_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STEPBYSTEP_MASTER_KEY", b64encode(b"too short").decode())

    with pytest.raises(MasterKeyError, match="9 bytes"), TestClient(app):
        pass


def test_the_backend_refuses_to_start_on_a_mailer_it_cannot_configure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same gate, for the same reason: a mailer that cannot send is found
    at boot rather than by the first person who asks for a Sign-in Code."""
    monkeypatch.setenv("STEPBYSTEP_MASTER_KEY", VALID)
    monkeypatch.setenv("MAILER", "smtp")
    monkeypatch.delenv("SMTP_HOST", raising=False)

    with pytest.raises(MailerConfigurationError, match="SMTP_HOST"), TestClient(app):
        pass


def test_the_master_key_is_the_decoded_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STEPBYSTEP_MASTER_KEY", VALID)

    assert master_key() == bytes(range(KEY_BYTES))
