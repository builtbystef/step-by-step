from datetime import datetime

from fastapi import APIRouter, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from step_by_step_api.accounts.sessions import CurrentUser
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import ApiError, errors
from step_by_step_api.extension import codes, package

router = APIRouter()

INSTALL_PAGE = "/extension"


class ExtensionVersion(BaseModel):
    current: str
    minimum_supported: str


@router.get(
    "/api/extension/version",
    operation_id="getExtensionVersion",
    responses=errors(503),
)
def get_extension_version() -> ExtensionVersion:
    return ExtensionVersion(
        current=package.current_version(),
        minimum_supported=package.MINIMUM_SUPPORTED_VERSION,
    )


@router.get(INSTALL_PAGE, include_in_schema=False)
def get_install_page() -> HTMLResponse:
    return HTMLResponse(
        package.install_page(current=package.current_version()),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/extension.zip", include_in_schema=False)
def download_extension() -> Response:
    version = package.current_version()
    return Response(
        content=package.archive(),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="step-by-step-extension-{version}.zip"'
            ),
            "Cache-Control": "no-store",
        },
    )


class ConnectCode(BaseModel):
    code: str
    expires_at: datetime


@router.post(
    "/api/extension/connect-codes",
    operation_id="createExtensionConnectCode",
    status_code=201,
    responses=errors(401),
)
def create_connect_code(user: CurrentUser, db: SessionDep) -> ConnectCode:
    code, expires_at = codes.issue(db, user)
    db.commit()
    return ConnectCode(code=code, expires_at=expires_at)


class ConnectRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class Connected(BaseModel):
    pass


@router.post(
    "/api/extension/connect",
    operation_id="connectExtension",
    responses=errors(401),
)
def connect_extension(asked: ConnectRequest, db: SessionDep) -> Connected:
    spent = codes.claim(db, asked.code)
    db.commit()
    if not spent:
        raise ApiError(401, "bad_code", "That connect code is not valid.")
    return Connected()
