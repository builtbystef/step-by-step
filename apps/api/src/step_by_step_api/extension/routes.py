"""The extension's HTTP surface: getting it, and pairing it with this instance.

Three of the four routes are unauthenticated on purpose. Somebody who cannot
sign in yet still has to be able to install the extension, and an app that
wants to say "your extension is out of date" has to be able to ask before
anyone has recorded anything.

The zip and the install page are documents a browser is pointed at rather than
calls the frontend makes, so they stay out of the generated client and out of
`/api` with it.
"""

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
"""Where the install sequence is written down, and what a refusal points at."""


class ExtensionVersion(BaseModel):
    """The two versions an instance and its extension have to agree about."""

    current: str
    minimum_supported: str


@router.get(
    "/api/extension/version",
    operation_id="getExtensionVersion",
    responses=errors(503),
)
def get_extension_version() -> ExtensionVersion:
    """What this instance serves, and the oldest it will record with.

    Unauthenticated: the app shows an out-of-date banner before a recording is
    attempted, and the extension has no session of its own to ask with.
    """
    return ExtensionVersion(
        current=package.current_version(),
        minimum_supported=package.MINIMUM_SUPPORTED_VERSION,
    )


@router.get(INSTALL_PAGE, include_in_schema=False)
def get_install_page() -> HTMLResponse:
    """The unpacked install sequence, served beside the build it describes."""
    return HTMLResponse(
        package.install_page(current=package.current_version()),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/extension.zip", include_in_schema=False)
def download_extension() -> Response:
    """The paired build, as the folder Chrome is pointed at."""
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
    """A one-time code the app shows, for the extension's popup to take."""

    code: str
    expires_at: datetime


@router.post(
    "/api/extension/connect-codes",
    operation_id="createExtensionConnectCode",
    status_code=201,
    responses=errors(401),
)
def create_connect_code(user: CurrentUser, db: SessionDep) -> ConnectCode:
    """Take a code to read out to the extension.

    Authenticated, because the code is this person authorizing the pairing:
    what spending it proves to the extension is that somebody signed into this
    instance meant to connect.
    """
    code, expires_at = codes.issue(db, user)
    db.commit()
    return ConnectCode(code=code, expires_at=expires_at)


class ConnectRequest(BaseModel):
    """What the extension presents: the code, however it was pasted."""

    code: str = Field(min_length=1, max_length=64)


class Connected(BaseModel):
    """Nothing — and deliberately.

    The extension learns that the address it was given is a live instance that
    accepted the pairing. Anything else here would be something an unauthenticated
    caller could ask this endpoint for.
    """


@router.post(
    "/api/extension/connect",
    operation_id="connectExtension",
    responses=errors(401),
)
def connect_extension(asked: ConnectRequest, db: SessionDep) -> Connected:
    """Spend a connect code.

    Unauthenticated: the extension has no session, which is the whole point of
    the code. The commit happens before the refusal for the same reason the
    Sign-in Code's does — a spent code must stay spent whatever the answer is.
    """
    spent = codes.claim(db, asked.code)
    db.commit()
    if not spent:
        raise ApiError(401, "bad_code", "That connect code is not valid.")
    return Connected()
