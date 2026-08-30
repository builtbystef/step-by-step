from base64 import b64encode
from collections.abc import Iterator

import pytest
from step_by_step_api.cli import main
from step_by_step_api.envelope import (
    KEY_BYTES,
    MASTER_KEY_VARIABLE,
    NEW_MASTER_KEY_VARIABLE,
    MasterKeyError,
    master_key,
)

VALID = b64encode(bytes(range(KEY_BYTES))).decode()


@pytest.fixture(autouse=True)
def uncached_keys() -> Iterator[None]:
    master_key.cache_clear()
    yield
    master_key.cache_clear()


@pytest.mark.parametrize(
    ("value", "match"),
    [
        (None, "not set"),
        ("not base64 at all!!", "base64"),
        (b64encode(b"too short").decode(), "9 bytes"),
    ],
)
def test_the_command_refuses_a_new_master_key_the_boot_gate_would_refuse(
    monkeypatch: pytest.MonkeyPatch, value: str | None, match: str
) -> None:
    monkeypatch.setenv(MASTER_KEY_VARIABLE, VALID)
    if value is None:
        monkeypatch.delenv(NEW_MASTER_KEY_VARIABLE, raising=False)
    else:
        monkeypatch.setenv(NEW_MASTER_KEY_VARIABLE, value)

    with pytest.raises(MasterKeyError, match=rf"{NEW_MASTER_KEY_VARIABLE}.*{match}"):
        main()
