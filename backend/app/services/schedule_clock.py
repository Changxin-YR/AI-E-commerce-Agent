"""Calendar recurrence, stored as naive UTC; fold=0, skip nonexistent wall times."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.schemas.schedules import ScheduleConfig


def wall_time(day: date, hour: int, minute: int, zone: ZoneInfo) -> datetime | None:
    local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=zone, fold=0)
    value = local.astimezone(UTC)
    if value.astimezone(zone).replace(tzinfo=None) != local.replace(tzinfo=None):
        return None
    return value.replace(tzinfo=None)


def occurrence(config: ScheduleConfig, at: datetime, *, future: bool) -> datetime:
    zone = ZoneInfo(config.timezone)
    day = at.replace(tzinfo=UTC).astimezone(zone).date()
    hour, minute = map(int, config.local_time.split(":"))
    for offset in range(400):
        candidate = day + timedelta(days=offset if future else -offset)
        if config.frequency == "weekly" and candidate.weekday() != config.weekday:
            continue
        if config.frequency == "monthly" and candidate.day != config.month_day:
            continue
        value = wall_time(candidate, hour, minute, zone)
        if value is not None and ((value > at) if future else (value <= at)):
            return value
    raise ValueError("No calendar occurrence within 400 days")


def notification_time(config: ScheduleConfig, now: datetime) -> datetime:
    if config.quiet_start is None or config.quiet_end is None:
        return now
    zone = ZoneInfo(config.timezone)
    start, end = config.quiet_start, config.quiet_end
    # Walk UTC minutes through offset transitions; bounded by two local days.
    for offset in range(2881):
        candidate = (
            now if offset == 0 else now.replace(second=0, microsecond=0) + timedelta(minutes=offset)
        )
        hour = candidate.replace(tzinfo=UTC).astimezone(zone).hour
        quiet = start <= hour < end if start < end else (hour >= start or hour < end)
        if not quiet:
            return candidate
    raise ValueError("Quiet hours exceed two days")
