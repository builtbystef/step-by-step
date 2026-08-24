"""The Organization's Secret vault and each member's Personal Override."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from step_by_step_core.db import Base


class Secret(Base):
    """A named encrypted value belonging to one Organization."""

    __tablename__ = "secrets"
    __table_args__ = (UniqueConstraint("org_id", "name", name="secrets_org_name_key"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    sealed_value: Mapped[bytes] = mapped_column(LargeBinary)
    sealed_data_key: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SecretOverride(Base):
    """One member's encrypted value layered over an Organization Secret."""

    __tablename__ = "secret_overrides"
    __table_args__ = (
        UniqueConstraint(
            "secret_id", "user_id", name="secret_overrides_secret_user_key"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    secret_id: Mapped[UUID] = mapped_column(
        ForeignKey("secrets.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    sealed_value: Mapped[bytes] = mapped_column(LargeBinary)
    sealed_data_key: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
