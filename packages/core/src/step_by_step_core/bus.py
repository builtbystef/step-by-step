"""The Redis seam: the dispatch pipe and the event bus, one client per process.

Redis carries Run ids to Workers and Run events back out; Postgres, never
Redis, holds the truth. Workers publish their events here directly rather than
through the backend.

The URL comes only from the `REDIS_URL` environment variable, on the same
terms as the database's, and the client is built on first use, so importing a
process needs no Redis.
"""

from functools import lru_cache
from os import environ

from redis import Redis

DISPATCH_LIST = "runs:dispatch"
"""The one list carrying queued Run ids to Workers."""


@lru_cache(maxsize=1)
def get_redis() -> Redis:
    """The process-wide client, built from the environment-supplied URL."""
    return Redis.from_url(environ["REDIS_URL"])
