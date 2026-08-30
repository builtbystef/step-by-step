import json

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession
from step_by_step_core.bus import control_channel, get_redis
from step_by_step_core.objects import artifact_bucket, object_store

from step_by_step_api import clock
from step_by_step_api.accounts.models import (
    Membership,
    Organization,
    Role,
    SigninCode,
    User,
)
from step_by_step_api.accounts.service import normalized
from step_by_step_api.errors import ApiError
from step_by_step_api.runs.models import NON_TERMINAL, Artifact, Run, RunStatus


def end_organization(db: DbSession, organization: Organization, typed: str) -> None:
    if typed.strip() != organization.name:
        raise mismatch("that is not this Organization's name")

    keys = list(
        db.execute(
            select(Artifact.object_key)
            .join(Run, Artifact.run_id == Run.id)
            .where(Run.org_id == organization.id)
        )
        .scalars()
        .all()
    )
    live = list(
        db.execute(
            select(Run)
            .where(Run.org_id == organization.id, Run.status.in_(NON_TERMINAL))
            .with_for_update()
            .order_by(Run.id)
        )
        .scalars()
        .all()
    )
    running_ids = [run.id for run in live if run.status is RunStatus.RUNNING]
    ended_at = clock.now()
    for run in live:
        run.status = RunStatus.CANCELLED
        run.ended_at = ended_at
    # Make cancellation observable before deleting artifacts.
    db.commit()
    for run_id in running_ids:
        get_redis().publish(
            control_channel(run_id), json.dumps({"cancel_requested": True})
        )

    bucket = artifact_bucket()
    store = object_store()
    for key in keys:
        store.delete_object(Bucket=bucket, Key=key)
    db.delete(organization)


def end_account(db: DbSession, user: User, typed: str) -> None:
    if normalized(typed) != normalized(user.email):
        raise mismatch("that is not this account's address")
    if owned_organizations(db, user):
        raise ApiError(
            403,
            "sole_owner",
            "you own an Organization; hand it on or end it first",
        )
    db.execute(delete(SigninCode).where(SigninCode.email == normalized(user.email)))
    db.delete(user)


def owned_organizations(db: DbSession, user: User) -> list[Organization]:
    return list(
        db.execute(
            select(Organization)
            .join(Membership, Membership.org_id == Organization.id)
            .where(Membership.user_id == user.id, Membership.role == Role.OWNER)
            .order_by(Organization.created_at)
        )
        .scalars()
        .all()
    )


def mismatch(message: str) -> ApiError:
    return ApiError(400, "confirmation_mismatch", message)
