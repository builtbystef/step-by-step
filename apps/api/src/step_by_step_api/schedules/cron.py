"""Cron parsing and next-occurrence, in the Schedule's IANA timezone."""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import CroniterBadCronError, CroniterBadDateError, croniter

from step_by_step_api.errors import ApiError


def require_timezone(name: str) -> ZoneInfo:
    """The named zone, or 400 invalid_timezone if IANA does not know it."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, KeyError) as error:
        raise ApiError(
            400, "invalid_timezone", "that is not an IANA timezone"
        ) from error


def require_cron(expression: str) -> None:
    """Refuse a string croniter will not iterate."""
    if not croniter.is_valid(expression):
        raise ApiError(400, "invalid_cron", "that is not a cron expression")


def next_occurrence(expression: str, timezone: str, after: datetime) -> datetime:
    """The next instant the expression matches, strictly after `after`, in that zone.

    `after` may be any aware datetime; the result is timezone-aware in `timezone`.
    """
    require_cron(expression)
    zone = require_timezone(timezone)
    local = after.astimezone(zone)
    try:
        nxt = croniter(expression, local).get_next(datetime)
    except (CroniterBadCronError, CroniterBadDateError) as error:
        raise ApiError(400, "invalid_cron", "that is not a cron expression") from error
    if nxt.tzinfo is None:
        nxt = nxt.replace(tzinfo=zone)
    return nxt
