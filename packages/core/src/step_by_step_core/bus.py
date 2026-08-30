from functools import lru_cache
from os import environ
from uuid import UUID

from redis import Redis

DISPATCH_LIST = "runs:dispatch"


def control_channel(run_id: UUID) -> str:
    return f"run:{run_id}:control"


@lru_cache(maxsize=1)
def get_redis() -> Redis:
    return Redis.from_url(environ["REDIS_URL"])
