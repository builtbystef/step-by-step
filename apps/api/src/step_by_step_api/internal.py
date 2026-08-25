"""The shared compose token that authenticates Worker → backend routes.

A fixed pool has no per-Worker provisioning step, so one token is the whole
posture (54i6da): present it, and also be acting on a non-terminal Run. The
token lives in the environment both processes already share.
"""

from hashlib import sha256
from hmac import compare_digest
from os import environ
from typing import Annotated

from fastapi import Depends, Header

from step_by_step_api.errors import ApiError

INTERNAL_TOKEN_VARIABLE = "INTERNAL_TOKEN"
"""The compose-supplied secret Workers send and the backend checks."""


def require_internal_token(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Refuse anything that does not present the shared token."""
    expected = environ.get(INTERNAL_TOKEN_VARIABLE, "")
    presented = bearer(authorization)
    if not expected or not same_secret(presented, expected):
        raise ApiError(401, "unauthenticated", "internal token required")


def bearer(authorization: str | None) -> str:
    if authorization is None:
        return ""
    prefix = "Bearer "
    if authorization.startswith(prefix):
        return authorization[len(prefix) :]
    return authorization


def same_secret(presented: str, expected: str) -> bool:
    """Compare without leaking the expected length through the timing."""
    return compare_digest(
        sha256(presented.encode()).digest(), sha256(expected.encode()).digest()
    )


InternalToken = Annotated[None, Depends(require_internal_token)]
