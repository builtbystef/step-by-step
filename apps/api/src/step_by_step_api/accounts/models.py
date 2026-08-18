"""The accounts tables.

Six of them, and they land together even though this slice animates only the
first four: a column a later slice fills is cheaper than a migration a later
slice writes. `attempts` is the throttling slice's, and `invitations` is the
Invitations slice's.

The tenant is the Organization (ADR 0005). Ownership cascades: rows an
Organization owns go with it, and the rows a user owns go with the user.
"""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from step_by_step_core.db import Base

EMAIL_LENGTH = 320
"""The longest address SMTP allows: 64 for the local part, 255 for the domain."""

HASH_LENGTH = 64
"""A SHA-256 digest in hex."""


class Role(StrEnum):
    """What a Membership lets a user do in its Organization.

    Exactly three, and an Organization has exactly one owner. Roles gate
    membership and lifecycle actions only — every role does the domain work.
    """

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


def role_column(name: str) -> Enum:
    """A role stored as its own word rather than as its Python name.

    `native_enum=False` keeps it a VARCHAR with a check constraint, so adding
    a role would be a migration rather than an ALTER TYPE — and the constraint
    needs a name of its own per table.
    """
    return Enum(
        Role,
        native_enum=False,
        length=16,
        name=name,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda enum: [member.value for member in enum],
    )


class User(Base):
    """One person. The email is the identity; there is nothing else to prove."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(EMAIL_LENGTH))
    display_name: Mapped[str | None] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Stored as entered and compared without case: `Ada@Example.com` is the
    # same person as `ada@example.com`, and the address they see is the one
    # they typed. The index is what makes both true at once.
    __table_args__ = (
        Index("users_email_lower_key", text("lower(email)"), unique=True),
    )


class Session(Base):
    """A signed-in browser. Revocation is deleting the row, and nothing else."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(HASH_LENGTH), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SigninCode(Base):
    """The outstanding Sign-in Code for one address.

    One row per address, because requesting a code replaces the last one: the
    newest code is the only code. `attempts` counts wrong guesses against it;
    capping them is the throttling slice's work.
    """

    __tablename__ = "signin_codes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(EMAIL_LENGTH), unique=True)
    code_hash: Mapped[str] = mapped_column(String(HASH_LENGTH))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Organization(Base):
    """The tenant. Everything the product makes belongs to exactly one."""

    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Membership(Base):
    """A user's place in one Organization, with the role that sets what they may do."""

    __tablename__ = "memberships"

    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[Role] = mapped_column(role_column("membership_role"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Invitation(Base):
    """An offer to join an Organization, which signing in with that address accepts.

    The Invitations slice animates this table; it lands here so that the
    accounts schema is one migration rather than two.
    """

    __tablename__ = "invitations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    org_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(EMAIL_LENGTH), index=True)
    role: Mapped[Role] = mapped_column(role_column("invitation_role"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
