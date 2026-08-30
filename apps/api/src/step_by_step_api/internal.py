from hashlib import sha256
from hmac import compare_digest
from os import environ
from typing import Annotated

from fastapi import Depends, Header

from step_by_step_api.errors import ApiError

INTERNAL_TOKEN_VARIABLE = "INTERNAL_TOKEN"


def require_internal_token(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
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
    return compare_digest(
        sha256(presented.encode()).digest(), sha256(expected.encode()).digest()
    )


InternalToken = Annotated[None, Depends(require_internal_token)]
