from collections.abc import Iterable
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from step_by_step_api import clock
from step_by_step_api.accounts.models import User
from step_by_step_api.accounts.orgs import ActiveMembership
from step_by_step_api.accounts.sessions import CurrentUser
from step_by_step_api.db import SessionDep
from step_by_step_api.envelope import Sealed, master_key, open_sealed, seal
from step_by_step_api.errors import ApiError, errors
from step_by_step_api.secrets.models import Secret, SecretOverride
from step_by_step_api.workflows.models import Workflow, WorkflowDraft, WorkflowVersion

router = APIRouter(prefix="/api/secrets", tags=["secrets"])
SecretValue = Annotated[str, Field(min_length=1)]
SecretName = Annotated[str, Field(min_length=1, max_length=200)]


class CreateSecret(BaseModel):
    name: SecretName
    value: SecretValue


class ChangeSecret(BaseModel):
    name: SecretName | None = None
    value: SecretValue | None = None

    @model_validator(mode="after")
    def has_change(self) -> ChangeSecret:
        if self.name is None and self.value is None:
            raise ValueError("name or value is required")
        return self


class OverrideValue(BaseModel):
    value: SecretValue


class SecretIdentity(BaseModel):
    id: UUID
    name: str


class OverrideSummary(BaseModel):
    updated_at: datetime


class SecretUsage(BaseModel):
    workflow_id: UUID
    workflow_name: str


class SecretSummary(SecretIdentity):
    updated_at: datetime
    used_by: list[SecretUsage]
    my_override: OverrideSummary | None


class RevealedValue(BaseModel):
    value: str


def in_organization(db: SessionDep, secret_id: UUID, org_id: UUID) -> Secret:
    found = db.execute(
        select(Secret).where(Secret.id == secret_id, Secret.org_id == org_id)
    ).scalar_one_or_none()
    if found is None:
        raise ApiError(404, "secret_not_found", "Secret not found")
    return found


def own_override(db: SessionDep, secret_id: UUID, user: User) -> SecretOverride | None:
    return db.execute(
        select(SecretOverride).where(
            SecretOverride.secret_id == secret_id, SecretOverride.user_id == user.id
        )
    ).scalar_one_or_none()


def sealed_text(value: str) -> Sealed:
    return seal(value.encode(), master_key())


def reveal(sealed_value: bytes, sealed_data_key: bytes) -> RevealedValue:
    plaintext = open_sealed(
        Sealed(value=sealed_value, data_key=sealed_data_key), master_key()
    )
    return RevealedValue(value=plaintext.decode())


def commit_unique(db: SessionDep) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "name_taken", "that Secret name is already used") from None


def bound_secret_id(variable: object) -> UUID | None:
    if not isinstance(variable, dict):
        return None
    raw = variable.get("secretId")
    if not isinstance(raw, str):
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


def usages_in(
    documents: Iterable[tuple[UUID, str, dict[str, Any]]],
) -> dict[UUID, list[SecretUsage]]:
    found: dict[UUID, dict[UUID, str]] = {}
    for workflow_id, workflow_name, document in documents:
        for variable in document.get("variables") or []:
            secret_id = bound_secret_id(variable)
            if secret_id is None:
                continue
            found.setdefault(secret_id, {})[workflow_id] = workflow_name
    return {
        secret_id: [
            SecretUsage(workflow_id=wid, workflow_name=name)
            for wid, name in sorted(bound.items(), key=lambda item: (item[1], item[0]))
        ]
        for secret_id, bound in found.items()
    }


def usages_for(db: SessionDep, org_id: UUID) -> dict[UUID, list[SecretUsage]]:
    drafts = db.execute(
        select(Workflow.id, Workflow.name, WorkflowDraft.document)
        .join(WorkflowDraft, WorkflowDraft.workflow_id == Workflow.id)
        .where(Workflow.org_id == org_id)
    ).all()
    versions = db.execute(
        select(Workflow.id, Workflow.name, WorkflowVersion.document)
        .join(WorkflowVersion, WorkflowVersion.workflow_id == Workflow.id)
        .where(Workflow.org_id == org_id)
    ).all()
    return usages_in(
        (workflow_id, name, document)
        for workflow_id, name, document in (*drafts, *versions)
    )


@router.get("", operation_id="listSecrets", response_model=list[SecretSummary])
def list_secrets(
    db: SessionDep, membership: ActiveMembership, user: CurrentUser
) -> list[SecretSummary]:
    rows = db.execute(
        select(Secret, SecretOverride)
        .outerjoin(
            SecretOverride,
            (SecretOverride.secret_id == Secret.id)
            & (SecretOverride.user_id == user.id),
        )
        .where(Secret.org_id == membership.org_id)
        .order_by(Secret.name, Secret.id)
    ).all()
    usages = usages_for(db, membership.org_id)
    return [
        SecretSummary(
            id=secret.id,
            name=secret.name,
            updated_at=secret.updated_at,
            used_by=usages.get(secret.id, []),
            my_override=(
                OverrideSummary(updated_at=override.updated_at)
                if override is not None
                else None
            ),
        )
        for secret, override in rows
    ]


@router.post("", operation_id="createSecret", status_code=201, responses=errors(409))
def create_secret(
    body: CreateSecret, db: SessionDep, membership: ActiveMembership
) -> SecretIdentity:
    return create_for_organization(body, db, membership.org_id)


def create_for_organization(
    body: CreateSecret, db: SessionDep, org_id: UUID
) -> SecretIdentity:
    sealed = sealed_text(body.value)
    secret = Secret(
        org_id=org_id,
        name=body.name,
        sealed_value=sealed.value,
        sealed_data_key=sealed.data_key,
    )
    db.add(secret)
    commit_unique(db)
    db.refresh(secret)
    return SecretIdentity(id=secret.id, name=secret.name)


@router.patch("/{secret_id}", operation_id="updateSecret", responses=errors(404, 409))
def update_secret(
    secret_id: UUID,
    body: ChangeSecret,
    db: SessionDep,
    membership: ActiveMembership,
) -> SecretIdentity:
    secret = in_organization(db, secret_id, membership.org_id)
    if body.name is not None:
        secret.name = body.name
    if body.value is not None:
        sealed = sealed_text(body.value)
        secret.sealed_value = sealed.value
        secret.sealed_data_key = sealed.data_key
    secret.updated_at = clock.now()
    commit_unique(db)
    return SecretIdentity(id=secret.id, name=secret.name)


@router.delete(
    "/{secret_id}", operation_id="deleteSecret", status_code=204, responses=errors(404)
)
def delete_secret(
    secret_id: UUID, db: SessionDep, membership: ActiveMembership
) -> Response:
    db.delete(in_organization(db, secret_id, membership.org_id))
    db.commit()
    return Response(status_code=204)


@router.post("/{secret_id}/reveal", operation_id="revealSecret", responses=errors(404))
def reveal_secret(
    secret_id: UUID, db: SessionDep, membership: ActiveMembership
) -> RevealedValue:
    secret = in_organization(db, secret_id, membership.org_id)
    return reveal(secret.sealed_value, secret.sealed_data_key)


@router.put(
    "/{secret_id}/override",
    operation_id="setSecretOverride",
    status_code=204,
    responses=errors(404),
)
def set_override(
    secret_id: UUID,
    body: OverrideValue,
    db: SessionDep,
    membership: ActiveMembership,
    user: CurrentUser,
) -> Response:
    secret = in_organization(db, secret_id, membership.org_id)
    stored = own_override(db, secret.id, user)
    sealed = sealed_text(body.value)
    if stored is None:
        stored = SecretOverride(
            secret_id=secret.id,
            user_id=user.id,
            sealed_value=sealed.value,
            sealed_data_key=sealed.data_key,
        )
        db.add(stored)
    else:
        stored.sealed_value = sealed.value
        stored.sealed_data_key = sealed.data_key
        stored.updated_at = clock.now()
    db.commit()
    return Response(status_code=204)


@router.delete(
    "/{secret_id}/override",
    operation_id="deleteSecretOverride",
    status_code=204,
    responses=errors(404),
)
def delete_override(
    secret_id: UUID,
    db: SessionDep,
    membership: ActiveMembership,
    user: CurrentUser,
) -> Response:
    secret = in_organization(db, secret_id, membership.org_id)
    db.execute(
        delete(SecretOverride).where(
            SecretOverride.secret_id == secret.id, SecretOverride.user_id == user.id
        )
    )
    db.commit()
    return Response(status_code=204)


@router.post(
    "/{secret_id}/override/reveal",
    operation_id="revealSecretOverride",
    responses=errors(404),
)
def reveal_override(
    secret_id: UUID,
    db: SessionDep,
    membership: ActiveMembership,
    user: CurrentUser,
) -> RevealedValue:
    secret = in_organization(db, secret_id, membership.org_id)
    stored = own_override(db, secret.id, user)
    if stored is None:
        raise ApiError(404, "no_override", "you have no Personal Override")
    return reveal(stored.sealed_value, stored.sealed_data_key)
