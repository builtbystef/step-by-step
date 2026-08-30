from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from step_by_step_core.db import Base


class AuthState(Base):
    __tablename__ = "auth_states"
    __table_args__ = (
        ForeignKeyConstraint(
            ["org_id", "user_id"],
            ["memberships.org_id", "memberships.user_id"],
            ondelete="CASCADE",
            name="auth_states_membership_fkey",
        ),
        UniqueConstraint(
            "org_id", "user_id", "domain", name="auth_states_personal_domain_key"
        ),
        Index(
            "auth_states_organization_domain_key",
            "org_id",
            "domain",
            unique=True,
            postgresql_where=text("user_id IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID | None] = mapped_column(index=True)
    domain: Mapped[str] = mapped_column(String(253))
    sealed_blob: Mapped[bytes] = mapped_column(LargeBinary)
    sealed_data_key: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
