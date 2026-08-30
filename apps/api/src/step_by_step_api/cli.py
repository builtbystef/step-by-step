from dataclasses import dataclass

from sqlalchemy import select
from step_by_step_core.db import session_scope

from step_by_step_api.auth_states.models import AuthState
from step_by_step_api.envelope import (
    NEW_MASTER_KEY_VARIABLE,
    master_key,
    read_master_key,
    rewrap,
)
from step_by_step_api.secrets.models import Secret, SecretOverride

SEALED_TABLES = (Secret, SecretOverride, AuthState)


@dataclass(frozen=True, slots=True)
class Rotation:
    rewrapped: int
    already_rotated: int


def rotate(current: bytes, new: bytes) -> Rotation:
    rewrapped = 0
    already_rotated = 0
    with session_scope() as session:
        for model in SEALED_TABLES:
            for row in session.scalars(select(model)).all():
                rotated = rewrap(row.sealed_data_key, current, new)
                if rotated is None:
                    already_rotated += 1
                    continue
                row.sealed_data_key = rotated
                session.commit()
                rewrapped += 1
    return Rotation(rewrapped=rewrapped, already_rotated=already_rotated)


def main() -> None:
    current = master_key()
    new = read_master_key(NEW_MASTER_KEY_VARIABLE)
    result = rotate(current, new)
    print(f"re-wrapped: {result.rewrapped}")
    print(f"already-rotated: {result.already_rotated}")


if __name__ == "__main__":
    main()
