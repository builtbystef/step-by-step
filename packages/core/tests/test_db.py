"""The database seam's configuration contract.

The URL comes from the environment and nowhere else, so that a misconfigured
process fails loudly instead of connecting to the wrong database. Building an
engine opens no connection, so this belongs in the fast tier.
"""

import pytest
from step_by_step_core.db import get_engine


@pytest.fixture(autouse=True)
def unconfigured_engine() -> None:
    """No test here may inherit — or leave behind — a cached engine."""
    get_engine.cache_clear()


def test_the_url_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db.example:5432/sbs")

    url = get_engine().url

    assert url.host == "db.example"
    assert url.database == "sbs"


def test_a_missing_url_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(KeyError, match="DATABASE_URL"):
        get_engine()


def test_one_engine_serves_the_whole_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db.example:5432/sbs")

    assert get_engine() is get_engine()
