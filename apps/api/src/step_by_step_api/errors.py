from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, **extra: Any) -> None:
        super().__init__(f"{status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra


def errors(*statuses: int) -> dict[int | str, dict[str, Any]]:
    return {status: {"model": ErrorBody} for status in statuses}


def install_error_handler(app: FastAPI) -> None:

    @app.exception_handler(ApiError)
    async def handle(request: Request, raised: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=raised.status,
            content={
                **ErrorBody(code=raised.code, message=raised.message).model_dump(),
                **raised.extra,
            },
        )
