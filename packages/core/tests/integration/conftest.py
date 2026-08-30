from collections.abc import Iterator
from uuid import uuid4

import pytest
from step_by_step_core.bus import get_redis
from step_by_step_core.db import get_engine
from step_by_step_core.objects import artifact_bucket, object_store, signing_store


@pytest.fixture(autouse=True)
def clients_built_from_the_real_environment() -> Iterator[None]:
    for cached in (get_engine, get_redis, object_store, signing_store):
        cached.cache_clear()
    yield
    for cached in (get_engine, get_redis, object_store, signing_store):
        cached.cache_clear()


@pytest.fixture
def object_key() -> Iterator[str]:
    key = f"tests/{uuid4().hex}"
    yield key
    object_store().delete_object(Bucket=artifact_bucket(), Key=key)
