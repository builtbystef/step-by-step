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


def _aware(instant: datetime, zone: ZoneInfo) -> datetime:
    if instant.tzinfo is None:
        return instant.replace(tzinfo=zone)
    return instant.astimezone(zone)


PREVIEW_COUNT = 5
"""How many future Occurrences the preview (and the detail) return."""


def next_occurrence(expression: str, timezone: str, after: datetime) -> datetime:
    """The next instant the expression matches, strictly after `after`, in that zone.

    `after` may be any aware datetime; the result is timezone-aware in `timezone`.
    """
    return next_occurrences(expression, timezone, after, count=1)[0]


def next_occurrences(
    expression: str, timezone: str, after: datetime, count: int = PREVIEW_COUNT
) -> list[datetime]:
    """The next `count` instants the expression matches, strictly after `after`."""
    require_cron(expression)
    zone = require_timezone(timezone)
    local = after.astimezone(zone) if after.tzinfo else after.replace(tzinfo=zone)
    walker = croniter(expression, local)
    found: list[datetime] = []
    for _ in range(count):
        try:
            found.append(_aware(walker.get_next(datetime), zone))
        except (CroniterBadCronError, CroniterBadDateError) as error:
            raise ApiError(
                400, "invalid_cron", "that is not a cron expression"
            ) from error
    return found


def occurrences_through(
    expression: str, timezone: str, start: datetime, until: datetime
) -> list[datetime]:
    """Each instant the expression matches, from `start` through `until` inclusive."""
    require_cron(expression)
    zone = require_timezone(timezone)
    start_local = start.astimezone(zone)
    until_local = until.astimezone(zone)
    if start_local > until_local:
        return []
    found: list[datetime] = []
    if croniter.match(expression, start_local):
        found.append(start_local)
    walker = croniter(expression, start_local)
    while True:
        try:
            nxt = _aware(walker.get_next(datetime), zone)
        except CroniterBadDateError:
            break
        if nxt > until_local:
            break
        found.append(nxt)
    return found
