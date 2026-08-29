"""The backend container's operator commands.

`rotate-master-key` re-wraps every sealed row's data key from
`STEPBYSTEP_MASTER_KEY` to `STEPBYSTEP_NEW_MASTER_KEY`. Record plaintexts are
never decrypted. The operator swaps the environment variables and restarts
the backend afterwards.
"""

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
"""Every table that stores a sealed data key. Rotation walks them all."""


@dataclass(frozen=True, slots=True)
class Rotation:
    """What one pass of `rotate-master-key` did."""

    rewrapped: int
    already_rotated: int


def rotate(current: bytes, new: bytes) -> Rotation:
    """Re-wrap every sealed data key from `current` to `new`.

    Each row is committed on its own so a pass interrupted halfway leaves a
    table the next pass can finish: `rewrap` reports a row the earlier pass
    already moved, and this writes nothing for it.
    """
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
    """Read both keys, rotate, print the two counts."""
    current = master_key()
    new = read_master_key(NEW_MASTER_KEY_VARIABLE)
    result = rotate(current, new)
    print(f"re-wrapped: {result.rewrapped}")
    print(f"already-rotated: {result.already_rotated}")


if __name__ == "__main__":
    main()
