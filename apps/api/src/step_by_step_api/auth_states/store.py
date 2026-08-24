"""Sealed, last-write-wins Auth State storage."""

from uuid import UUID, uuid4

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from step_by_step_api import clock
from step_by_step_api.auth_states.blob import AuthStateBlob
from step_by_step_api.auth_states.models import AuthState
from step_by_step_api.envelope import master_key, seal


def store(
    db: Session, org_id: UUID, user_id: UUID | None, blob: AuthStateBlob
) -> AuthState:
    """Insert or replace one destination while retaining its row identity."""
    sealed = seal(blob.model_dump_json(by_alias=True).encode(), master_key())
    row_id = uuid4()
    statement = insert(AuthState).values(
        id=row_id,
        org_id=org_id,
        user_id=user_id,
        domain=blob.domain,
        sealed_blob=sealed.value,
        sealed_data_key=sealed.data_key,
    )
    replacement = {
        "sealed_blob": statement.excluded.sealed_blob,
        "sealed_data_key": statement.excluded.sealed_data_key,
        "updated_at": clock.now(),
    }
    if user_id is None:
        statement = statement.on_conflict_do_update(
            index_elements=[AuthState.org_id, AuthState.domain],
            index_where=AuthState.user_id.is_(None),
            set_=replacement,
        )
    else:
        statement = statement.on_conflict_do_update(
            constraint="auth_states_personal_domain_key", set_=replacement
        )
    stored_id = db.execute(statement.returning(AuthState.id)).scalar_one()
    return db.get_one(AuthState, stored_id)
