from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import CroniterBadCronError, CroniterBadDateError, croniter

from step_by_step_api.errors import ApiError


def require_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, KeyError) as error:
        raise ApiError(
            400, "invalid_timezone", "that is not an IANA timezone"
        ) from error


def require_cron(expression: str) -> None:
    if not croniter.is_valid(expression):
        raise ApiError(400, "invalid_cron", "that is not a cron expression")


def _aware(instant: datetime, zone: ZoneInfo) -> datetime:
    if instant.tzinfo is None:
        return instant.replace(tzinfo=zone)
    return instant.astimezone(zone)


PREVIEW_COUNT = 5


def next_occurrence(expression: str, timezone: str, after: datetime) -> datetime:
    return next_occurrences(expression, timezone, after, count=1)[0]


def next_occurrences(
    expression: str, timezone: str, after: datetime, count: int = PREVIEW_COUNT
) -> list[datetime]:
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
