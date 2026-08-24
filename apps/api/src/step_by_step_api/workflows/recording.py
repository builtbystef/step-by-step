"""Recording-session capabilities, checkpoints, and Draft finalization."""

import hashlib
import re
import secrets
from copy import deepcopy
from datetime import timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, Response
from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import select

from step_by_step_api import clock
from step_by_step_api.accounts.orgs import ActiveMembership
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import ApiError, errors
from step_by_step_api.extension import package
from step_by_step_api.extension.routes import INSTALL_PAGE
from step_by_step_api.workflows import document
from step_by_step_api.workflows.document import SelectorCandidate, WorkflowDocument
from step_by_step_api.workflows.models import (
    RecordingMode,
    RecordingSession,
    WorkflowDraft,
)
from step_by_step_api.workflows.routes import draft_of

router = APIRouter()
SESSION_LIFETIME = timedelta(hours=1)
TOKEN_BYTES = 32
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def version_tuple(version: str) -> tuple[int, int, int] | None:
    matched = VERSION.fullmatch(version)
    if matched is None:
        return None
    major, minor, patch = matched.groups()
    return int(major), int(minor), int(patch)


def require_supported_version(version: str | None) -> None:
    if version is None:
        raise ApiError(
            400,
            "extension_version_required",
            "X-Extension-Version is required to start recording.",
        )
    offered = version_tuple(version)
    minimum = version_tuple(package.MINIMUM_SUPPORTED_VERSION)
    if offered is None or minimum is None or offered < minimum:
        raise ApiError(
            409,
            "extension_update_required",
            f"Update the extension at {INSTALL_PAGE} before recording; "
            f"this instance requires {package.MINIMUM_SUPPORTED_VERSION} or newer.",
        )


class MintRequest(BaseModel):
    """A new scope, or the id of an expired scope whose buffer must survive."""

    session_id: UUID | None = None
    mode: RecordingMode = RecordingMode.RECORD
    step_id: UUID | None = None

    @model_validator(mode="after")
    def mode_has_the_right_step(self) -> MintRequest:
        if self.session_id is not None:
            return self
        if self.mode is RecordingMode.REPICK and self.step_id is None:
            raise ValueError("a repick session requires step_id")
        if self.mode is RecordingMode.RECORD and self.step_id is not None:
            raise ValueError("step_id belongs only to a repick session")
        return self


class MintedSession(BaseModel):
    session_id: UUID
    token: str


@router.post(
    "/api/workflows/{workflow_id}/recording-sessions",
    operation_id="createRecordingSession",
    status_code=201,
    responses=errors(400, 401, 403, 404, 409),
)
def mint_session(
    workflow_id: UUID,
    asked: MintRequest,
    member: ActiveMembership,
    db: SessionDep,
    extension_version: Annotated[
        str | None, Header(alias="X-Extension-Version")
    ] = None,
) -> MintedSession:
    """Mint or rotate a one-hour token for this user and this Draft."""
    require_supported_version(extension_version)
    draft = draft_of(db, member, workflow_id)
    if asked.session_id is None:
        if asked.mode is RecordingMode.REPICK:
            assert asked.step_id is not None
            if not any(
                step.get("id") == str(asked.step_id)
                for step in draft.document.get("steps", [])
            ):
                raise ApiError(404, "step_not_found", "no such Step in this Draft")
        session = RecordingSession(
            workflow_id=workflow_id,
            user_id=member.user_id,
            token_hash="",
            expires_at=clock.now() + SESSION_LIFETIME,
            mode=asked.mode,
            step_id=asked.step_id,
        )
        db.add(session)
    else:
        session = db.execute(
            select(RecordingSession)
            .where(
                RecordingSession.id == asked.session_id,
                RecordingSession.workflow_id == workflow_id,
                RecordingSession.user_id == member.user_id,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if session is None:
            raise ApiError(
                404, "recording_session_not_found", "no such recording session"
            )
        if session.finalized_at is not None:
            raise ApiError(
                409,
                "recording_session_finalized",
                "this recording session is finalized",
            )
    token = secrets.token_urlsafe(TOKEN_BYTES)
    session.token_hash = token_digest(token)
    session.expires_at = clock.now() + SESSION_LIFETIME
    db.commit()
    return MintedSession(session_id=session.id, token=token)


class Checkpoint(BaseModel):
    seq: int = Field(ge=0)
    steps: list[dict[str, Any]]


def authorized_session(
    db: SessionDep, session_id: UUID, authorization: str | None
) -> RecordingSession:
    token = authorization or ""
    if token.lower().startswith("bearer "):
        token = token[7:]
    found = db.execute(
        select(RecordingSession)
        .where(
            RecordingSession.id == session_id,
            RecordingSession.token_hash == token_digest(token),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if found is None or found.expires_at <= clock.now():
        raise ApiError(
            401, "invalid_recording_token", "the recording token is invalid or expired"
        )
    if found.finalized_at is not None:
        raise ApiError(
            409, "recording_session_finalized", "this recording session is finalized"
        )
    return found


@router.post(
    "/api/recording-sessions/{session_id}/checkpoint",
    operation_id="checkpointRecordingSession",
    status_code=204,
    responses=errors(401, 409),
)
def save_checkpoint(
    session_id: UUID,
    checkpoint: Checkpoint,
    db: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> Response:
    """Keep only the newest full buffer; repeating a sequence changes nothing."""
    session = authorized_session(db, session_id, authorization)
    if session.mode is not RecordingMode.RECORD:
        raise ApiError(
            409, "wrong_recording_mode", "a repick session has no step buffer"
        )
    if session.checkpoint_seq is None or checkpoint.seq > session.checkpoint_seq:
        session.checkpoint_seq = checkpoint.seq
        session.checkpoint_steps = checkpoint.steps
    db.commit()
    return Response(status_code=204)


class FinalizeRequest(BaseModel):
    steps: list[dict[str, Any]] | None = None
    variables: list[dict[str, Any]] | None = None
    candidates: list[SelectorCandidate] | None = None


def validated_document(raw: dict[str, Any]) -> WorkflowDocument:
    try:
        parsed = WorkflowDocument.model_validate(raw)
    except ValidationError as invalid:
        raise document.shape_refusal(list(invalid.errors())) from None
    return document.validated(parsed)


def has_needs_secret(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("needsSecret") is True or value.get("needs-secret") is True:
            return True
        return any(has_needs_secret(part) for part in value.values())
    if isinstance(value, list):
        return any(has_needs_secret(part) for part in value)
    return False


@router.post(
    "/api/recording-sessions/{session_id}/finalize",
    operation_id="finalizeRecordingSession",
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
    responses=errors(400, 401, 409),
)
def finalize_session(
    session_id: UUID,
    asked: FinalizeRequest,
    db: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> WorkflowDocument:
    """Replace the Draft from a recording, or patch one Re-pick target."""
    session = authorized_session(db, session_id, authorization)
    draft = db.execute(
        select(WorkflowDraft)
        .where(WorkflowDraft.workflow_id == session.workflow_id)
        .with_for_update()
    ).scalar_one()
    if session.mode is RecordingMode.REPICK:
        saved = finalize_repick(session, draft, asked)
    else:
        steps = asked.steps if asked.steps is not None else session.checkpoint_steps
        if steps is None or asked.variables is None:
            raise ApiError(
                400, "incomplete_recording", "finalize requires steps and variables"
            )
        if has_needs_secret(steps):
            raise ApiError(
                400,
                "needs_secret",
                "Bind every password field to a secret Variable before saving.",
            )
        saved = validated_document({"steps": steps, "variables": asked.variables})
    draft.document = document.stored(saved)
    session.finalized_at = clock.now()
    db.commit()
    return saved


def finalize_repick(
    session: RecordingSession, draft: WorkflowDraft, asked: FinalizeRequest
) -> WorkflowDocument:
    if (
        asked.candidates is None
        or asked.steps is not None
        or asked.variables is not None
    ):
        raise ApiError(
            400, "invalid_repick", "a Re-pick finalize carries one candidate list"
        )
    changed = deepcopy(draft.document)
    for step in changed.get("steps", []):
        if step.get("id") != str(session.step_id):
            continue
        target = step.get("payload", {}).get("target")
        if not isinstance(target, dict):
            raise ApiError(400, "invalid_repick", "this Step has no target to Re-pick")
        target["candidates"] = [
            candidate.model_dump(mode="json", by_alias=True, exclude_none=True)
            for candidate in asked.candidates
        ]
        return validated_document(changed)
    raise ApiError(404, "step_not_found", "the scoped Step is no longer in this Draft")
