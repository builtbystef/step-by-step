import logging
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, field_serializer
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from step_by_step_api.auth_states.blob import AuthStateBlob
from step_by_step_api.auth_states.domains import registrable_domain
from step_by_step_api.auth_states.models import AuthState
from step_by_step_api.auth_states.store import open_blob, store
from step_by_step_api.envelope import Sealed, master_key, open_sealed
from step_by_step_api.errors import ApiError
from step_by_step_api.runs.models import (
    AuthStateConsentScope,
    Run,
    RunAuthStateCandidate,
)
from step_by_step_api.secrets.models import Secret, SecretOverride
from step_by_step_api.workflows.models import WorkflowVersion

log = logging.getLogger(__name__)


class ResolvedSecret(BaseModel):
    variable_name: str
    value: str


class Credentials(BaseModel):
    secrets: list[ResolvedSecret]
    auth_states: list[AuthStateBlob]

    @field_serializer("auth_states")
    def playwright_blobs(self, blobs: list[AuthStateBlob]) -> list[dict[str, Any]]:
        return [blob.model_dump(mode="json", by_alias=True) for blob in blobs]


class ConsentedDomains(BaseModel):
    domains: list[str]


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


def document_for(db: Session, run: Run) -> dict[str, Any]:
    if run.draft_snapshot is not None:
        return run.draft_snapshot
    if run.version_number is None:
        return {}
    version = db.get(WorkflowVersion, (run.workflow_id, run.version_number))
    if version is None:
        return {}
    return version.document


def secret_variables(document: dict[str, Any]) -> list[tuple[str, UUID | None]]:
    found: list[tuple[str, UUID | None]] = []
    for variable in document.get("variables") or []:
        if not isinstance(variable, dict) or not variable.get("secret"):
            continue
        name = variable.get("name")
        if not isinstance(name, str):
            continue
        found.append((name, bound_secret_id(variable)))
    return found


def missing_secret_names(
    db: Session, org_id: UUID, document: dict[str, Any]
) -> list[str]:
    missing: list[str] = []
    for name, secret_id in secret_variables(document):
        if secret_id is None:
            missing.append(name)
            continue
        found = db.execute(
            select(Secret.id).where(Secret.id == secret_id, Secret.org_id == org_id)
        ).scalar_one_or_none()
        if found is None:
            missing.append(name)
    return missing


def refuse_missing(names: list[str]) -> None:
    if names:
        raise ApiError(
            409,
            "missing_secret",
            "a Secret this Workflow needs is missing",
            variable_names=names,
        )


def open_text(sealed_value: bytes, sealed_data_key: bytes) -> str:
    return open_sealed(
        Sealed(value=sealed_value, data_key=sealed_data_key), master_key()
    ).decode()


def resolve_secrets(
    db: Session, run: Run, document: dict[str, Any]
) -> list[ResolvedSecret]:
    refuse_missing(missing_secret_names(db, run.org_id, document))
    resolved: list[ResolvedSecret] = []
    for name, secret_id in secret_variables(document):
        assert secret_id is not None
        secret = db.execute(
            select(Secret).where(Secret.id == secret_id, Secret.org_id == run.org_id)
        ).scalar_one()
        value = open_text(secret.sealed_value, secret.sealed_data_key)
        if run.starter_user_id is not None:
            override = db.execute(
                select(SecretOverride).where(
                    SecretOverride.secret_id == secret.id,
                    SecretOverride.user_id == run.starter_user_id,
                )
            ).scalar_one_or_none()
            if override is not None:
                value = open_text(override.sealed_value, override.sealed_data_key)
        resolved.append(ResolvedSecret(variable_name=name, value=value))
    return resolved


def resolve_auth_states(db: Session, run: Run) -> list[AuthStateBlob]:
    org_rows = db.execute(
        select(AuthState).where(
            AuthState.org_id == run.org_id, AuthState.user_id.is_(None)
        )
    ).scalars()
    by_domain = {row.domain: row for row in org_rows}
    if run.starter_user_id is not None:
        personal_rows = db.execute(
            select(AuthState).where(
                AuthState.org_id == run.org_id,
                AuthState.user_id == run.starter_user_id,
            )
        ).scalars()
        for row in personal_rows:
            by_domain[row.domain] = row
    return [
        open_blob(row) for row in sorted(by_domain.values(), key=lambda row: row.domain)
    ]


def credentials_for(db: Session, run: Run) -> Credentials:
    document = document_for(db, run)
    credentials = Credentials(
        secrets=resolve_secrets(db, run, document),
        auth_states=resolve_auth_states(db, run),
    )
    log.info("issued credentials for run %s", run.id)
    return credentials


def consented_domains(db: Session, run_id: UUID) -> list[str]:
    rows = db.execute(
        select(RunAuthStateCandidate.domain)
        .where(
            RunAuthStateCandidate.run_id == run_id,
            RunAuthStateCandidate.consent_scope.is_not(None),
        )
        .order_by(RunAuthStateCandidate.domain)
    ).scalars()
    return list(rows)


def layer(
    db: Session, org_id: UUID, user_id: UUID | None, domain: str
) -> AuthState | None:
    query = select(AuthState).where(
        AuthState.org_id == org_id, AuthState.domain == domain
    )
    query = (
        query.where(AuthState.user_id.is_(None))
        if user_id is None
        else query.where(AuthState.user_id == user_id)
    )
    return db.execute(query).scalar_one_or_none()


def candidate_for(
    db: Session, run_id: UUID, domain: str
) -> RunAuthStateCandidate | None:
    return db.execute(
        select(RunAuthStateCandidate).where(
            RunAuthStateCandidate.run_id == run_id,
            RunAuthStateCandidate.domain == domain,
        )
    ).scalar_one_or_none()


def write_destination(db: Session, run: Run, domain: str) -> UUID | None:
    if run.starter_user_id is not None and layer(
        db, run.org_id, run.starter_user_id, domain
    ):
        return run.starter_user_id
    if layer(db, run.org_id, None, domain):
        return None
    candidate = candidate_for(db, run.id, domain)
    if candidate is None or candidate.consent_scope is None:
        raise ApiError(
            400,
            "unconsented_domain",
            "that domain has no saved login and no consent",
            domain=domain,
        )
    if candidate.consent_scope is AuthStateConsentScope.PERSONAL:
        if candidate.consenting_user_id is None:
            raise ApiError(
                400,
                "unconsented_domain",
                "that domain has no saved login and no consent",
                domain=domain,
            )
        return candidate.consenting_user_id
    return None


def record_candidates(db: Session, run: Run, domains: list[str]) -> None:
    for raw in domains:
        try:
            domain = registrable_domain(raw)
        except ValueError as refused:
            raise ApiError(400, "invalid_domain", str(refused)) from refused
        statement = insert(RunAuthStateCandidate).values(
            id=uuid4(), run_id=run.id, domain=domain
        )
        db.execute(
            statement.on_conflict_do_nothing(
                constraint="run_auth_state_candidates_run_domain_key"
            )
        )


def write_auth_states(
    db: Session, run: Run, states: list[AuthStateBlob], new_candidates: list[str]
) -> None:
    destinations = [(blob, write_destination(db, run, blob.domain)) for blob in states]
    for blob, user_id in destinations:
        store(db, run.org_id, user_id, blob)
    record_candidates(db, run, new_candidates)
