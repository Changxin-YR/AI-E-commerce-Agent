from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StrictBool, field_validator

from app.schemas.common import InputModel, OutputModel
from app.schemas.support import PositiveId


class ReviewReply(InputModel):
    expected_version: PositiveId
    target_language: Literal["en", "zh"]
    confirmed: StrictBool


class ManualActionDetails(InputModel):
    method: Annotated[str, Field(min_length=2, max_length=80)]
    evidence_ref: Annotated[str, Field(min_length=2, max_length=500)]
    note: Annotated[str, Field(max_length=1000)] = ""


class RecordManualAction(ManualActionDetails):
    request_id: UUID
    expected_version: PositiveId
    occurred_at: datetime
    confirmed: StrictBool

    @field_validator("occurred_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None or value.year < 1000:
            raise ValueError("操作时间须包含时区偏移")
        return value.astimezone(UTC)


class ManualActionOutput(OutputModel):
    id: int
    draft_id: int
    draft_version: int
    occurred_at: str
    recorded_at: str
    details: ManualActionDetails | None
    provenance: Literal["seller_reported"] = "seller_reported"
    external_status: Literal["not_submitted"] = "not_submitted"


class SupportDelivery(OutputModel):
    draft_id: int
    version: int
    target_language: str
    checked_at: str
    plain_text: str
    csv_text: str
    filename: str
    external_status: Literal["not_submitted"] = "not_submitted"
