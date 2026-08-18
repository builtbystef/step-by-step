"""The integration tier's fixtures for the shared library.

Every test here runs against the real compose stack. That stack is long-lived
shared state, so nothing may assume it starts fresh: these tests read without
writing, or write under a key of their own and remove it afterwards.
"""

from collections.abc import Iterator
from uuid import uuid4

import pytest
from step_by_step_core.bus import get_redis
from step_by_step_core.db import get_engine
from step_by_step_core.objects import artifact_bucket, object_store, signing_store


@pytest.fixture(autouse=True)
def clients_built_from_the_real_environment() -> Iterator[None]:
    """Drop any client the fast tier cached from its fake environment."""
    for cached in (get_engine, get_redis, object_store, signing_store):
        cached.cache_clear()
    yield
    for cached in (get_engine, get_redis, object_store, signing_store):
        cached.cache_clear()


@pytest.fixture
def object_key() -> Iterator[str]:
    """A key this test owns, removed afterwards however the test ends."""
    key = f"tests/{uuid4().hex}"
    yield key
    object_store().delete_object(Bucket=artifact_bucket(), Key=key)
