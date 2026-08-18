"""The error shape the HTTP contract promises: JSON with a machine-readable code.

A client decides what to do from `code`, never from prose: the sign-in screen
tells a wrong code from a closed instance by that field alone. `message` is
for a developer reading a response, and no screen parses it.
"""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorBody(BaseModel):
    """What every refusal this application raises looks like."""

    code: str
    message: str


class ApiError(Exception):
    """A refusal with a status and a code, raised from anywhere in a request."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message


def errors(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """The `responses=` entry that puts `ErrorBody` in the generated client.

    Without it the schema would describe a refusal as an untyped object, and
    the frontend would read `code` off a value the compiler knows nothing
    about.
    """
    return {status: {"model": ErrorBody} for status in statuses}


def install_error_handler(app: FastAPI) -> None:
    """Teach the app to answer an `ApiError` with the shape above."""

    @app.exception_handler(ApiError)
    async def handle(request: Request, raised: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=raised.status,
            content=ErrorBody(code=raised.code, message=raised.message).model_dump(),
        )
