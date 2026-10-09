"""Completed calendar reporting windows, anchored to the intended occurrence."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.schemas.overview import OverviewScope
from app.schemas.schedules import ScheduleConfig


def previous_month(day: date) -> date:
    return (day.replace(day=1) - timedelta(days=1)).replace(day=1)


def report_scope(config: ScheduleConfig, shop: int, scheduled: datetime) -> OverviewScope:
    end = scheduled.replace(tzinfo=UTC).astimezone(ZoneInfo(config.timezone)).date()
    if config.frequency == "monthly":
        end = end.replace(day=1)
        start = previous_month(end)
        comparison_start = previous_month(start)
    else:
        days = 7 if config.frequency == "weekly" else 1
        if config.frequency == "weekly":
            end -= timedelta(days=end.weekday())
        start = end - timedelta(days=days)
        comparison_start = start - timedelta(days=days)
    return OverviewScope(
        shop_ids=[shop],
        start_date=start,
        end_date=end,
        comparison_start=comparison_start,
        comparison_end=start,
        timezone=config.timezone,
        data_identity=config.data_identity,
        currencies=config.report_currencies,
        max_age_hours=config.max_age_hours,
        min_quantity=config.min_quantity,
        max_margin_percent=config.max_margin_percent,
    )
