"""baseline

The empty first revision. It creates no table — the accounts slice writes the
first ones — but it gives the migration runner a head to reach, so that
`alembic upgrade head` against a fresh database is a real, repeatable step.

Revision ID: 14699da4a661
Revises:
Create Date: 2026-08-18 02:29:27.347481

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "14699da4a661"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
