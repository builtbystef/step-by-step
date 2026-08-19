"""The connect code table.

One row per outstanding code, holding a digest and never the code, exactly as
`signin_codes` does and for the same reason: a leaked backup must hand nobody a
working pairing.
"""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column
from step_by_step_core.db import Base

from step_by_step_api.accounts.models import HASH_LENGTH


class ExtensionConnectCode(Base):
    """A one-time code a signed-in user showed, for an extension to spend.

    It belongs to the user who took it, and goes with them: the code is that
    person authorizing a pairing, and it means nothing once they are gone.
    """

    __tablename__ = "extension_connect_codes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[str] = mapped_column(String(HASH_LENGTH), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
