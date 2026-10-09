from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StrictBool, model_validator

from app.schemas.common import Currency, InputModel, OutputModel, Timezone
from app.schemas.imports import DataIdentity, SourceChannel


class ScheduleConfig(InputModel):
    name: Annotated[str, Field(min_length=1, max_length=80)]
    timezone: Timezone
    frequency: Literal["daily", "weekly", "monthly"] = "daily"
    local_time: Annotated[str, Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")] = "09:00"
    weekday: Annotated[int, Field(ge=0, le=6)] = 0
    month_day: Annotated[int, Field(ge=1, le=28)] = 1
    lookback_days: Annotated[int, Field(ge=1, le=365)] = 7
    channel: SourceChannel = "generic"
    data_identity: DataIdentity
    currency: Currency
    rule_revision_id: Annotated[int, Field(ge=0)] = 0
    max_age_hours: Annotated[int, Field(ge=1, le=720)] = 24
    min_quantity: Annotated[int, Field(ge=1, le=1000000)] = 1
    max_margin_percent: Annotated[Decimal, Field(ge=-1000, le=100, decimal_places=2)] = Decimal(20)
    quiet_start: Annotated[int, Field(ge=0, le=23)] | None = None
    quiet_end: Annotated[int, Field(ge=0, le=23)] | None = None

    @model_validator(mode="after")
    def quiet_hours(self) -> Self:
        if (self.quiet_start is None) != (self.quiet_end is None):
            raise ValueError("免打扰起止小时须同时设置")
        if self.quiet_start is not None and self.quiet_start == self.quiet_end:
            raise ValueError("免打扰起止小时不能相同")
        return self


class CreateSchedule(InputModel):
    request_id: UUID
    config: ScheduleConfig
    confirmed: StrictBool


class ScheduleAction(InputModel):
    version: Annotated[int, Field(ge=1)]
    action: Literal["pause", "resume", "revoke", "edit"]
    config: ScheduleConfig | None = None
    confirmed: StrictBool = False


class ManualCheck(InputModel):
    request_id: UUID
    version: Annotated[int, Field(ge=1)]


class ScheduleOutput(OutputModel):
    id: int
    shop_id: int
    status: str
    version: int
    config: ScheduleConfig
    next_run_at: str | None
    created_at: str


class OccurrenceOutput(OutputModel):
    id: int
    shop_id: int
    schedule_id: int
    schedule_version: int
    trigger: str
    scheduled_at: str
    coalesced_from: str | None
    execution_id: int | None
    status: str
    reason: str
    notify_at: str
    read_at: str | None
    created_at: str
