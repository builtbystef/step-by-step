"""Saved logins visible to one active Organization member."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import or_, select

from step_by_step_api.accounts.orgs import ActiveMembership
from step_by_step_api.accounts.sessions import CurrentUser
from step_by_step_api.auth_states.models import AuthState
from step_by_step_api.db import SessionDep
from step_by_step_api.errors import ApiError, errors

router = APIRouter(prefix="/api/auth-states", tags=["auth-states"])


class AuthStateScope(StrEnum):
    ORGANIZATION = "organization"
    PERSONAL = "personal"


class AuthStateSummary(BaseModel):
    id: UUID
    domain: str
    scope: AuthStateScope
    created_at: datetime
    updated_at: datetime


def visible_to(state: AuthState, user_id: UUID) -> bool:
    return state.user_id is None or state.user_id == user_id


@router.get("", operation_id="listAuthStates")
def list_auth_states(
    db: SessionDep, membership: ActiveMembership, user: CurrentUser
) -> list[AuthStateSummary]:
    states = db.execute(
        select(AuthState)
        .where(
            AuthState.org_id == membership.org_id,
            or_(AuthState.user_id.is_(None), AuthState.user_id == user.id),
        )
        .order_by(AuthState.domain, AuthState.user_id.is_not(None), AuthState.id)
    ).scalars()
    return [
        AuthStateSummary(
            id=state.id,
            domain=state.domain,
            scope=(
                AuthStateScope.ORGANIZATION
                if state.user_id is None
                else AuthStateScope.PERSONAL
            ),
            created_at=state.created_at,
            updated_at=state.updated_at,
        )
        for state in states
    ]


@router.delete(
    "/{auth_state_id}",
    operation_id="deleteAuthState",
    status_code=204,
    responses=errors(404),
)
def delete_auth_state(
    auth_state_id: UUID,
    db: SessionDep,
    membership: ActiveMembership,
    user: CurrentUser,
) -> Response:
    state = db.execute(
        select(AuthState).where(
            AuthState.id == auth_state_id, AuthState.org_id == membership.org_id
        )
    ).scalar_one_or_none()
    if state is None or not visible_to(state, user.id):
        raise ApiError(404, "auth_state_not_found", "Saved login not found")
    db.delete(state)
    db.commit()
    return Response(status_code=204)
