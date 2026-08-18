"""The one place the current time enters the application.

Sign-in Codes expire, sessions slide, and Invitations run out — three
behaviours whose tests would otherwise have to wait real minutes. Every one of
them asks this module rather than `datetime` directly, so a test moves the
clock by replacing one function.
"""

from datetime import UTC, datetime


def now() -> datetime:
    """The current moment, always timezone-aware and always UTC."""
    return datetime.now(UTC)
