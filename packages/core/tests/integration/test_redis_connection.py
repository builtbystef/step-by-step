import pytest
from step_by_step_core.bus import get_redis

pytestmark = pytest.mark.integration


def test_a_worker_reaches_redis() -> None:
    assert get_redis().ping() is True
