"""The Redis seam's configuration contract.

Redis is the dispatch pipe and the event bus. Its URL comes from the
environment on the same terms as the database's, and building the client opens
no connection, so this belongs in the fast tier.
"""

from uuid import UUID

import pytest
from step_by_step_core.bus import control_channel, get_redis


@pytest.fixture(autouse=True)
def unconfigured_client() -> None:
    """No test here may inherit — or leave behind — a cached client."""
    get_redis.cache_clear()


def test_the_url_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://bus.example:6379/3")

    pool = get_redis().connection_pool

    assert pool.connection_kwargs["host"] == "bus.example"
    assert pool.connection_kwargs["db"] == 3


def test_a_missing_url_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)

    with pytest.raises(KeyError, match="REDIS_URL"):
        get_redis()


def test_one_client_serves_the_whole_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://bus.example:6379/3")

    assert get_redis() is get_redis()


def test_a_run_control_channel_is_addressed_by_its_id() -> None:
    run_id = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

    assert control_channel(run_id) == (
        "run:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee:control"
    )
