from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.analytics import AnalysisInput, SourceReference
from app.schemas.common import InputModel, OutputModel
from app.schemas.imports import DataIdentity, SourceChannel


class OperationScope(AnalysisInput):
    rule_revision_id: Annotated[int, Field(ge=0)] = 0
    intent: Literal["low_margin"] = "low_margin"
    channel: SourceChannel = "generic"
    max_age_hours: Annotated[int, Field(ge=1, le=720)] = 24


class RunInput(InputModel):
    request_id: UUID
    scope: OperationScope


class TaskQuery(InputModel):
    data_identity: DataIdentity = "user_import"
    channel: SourceChannel = "generic"
    offset: Annotated[int, Field(ge=0, le=1000000)] = 0


TaskAction = Literal["approve", "reject", "ignore", "defer", "complete", "reopen", "edit"]


class TaskInput(InputModel):
    version: Annotated[int, Field(ge=1)]
    action: TaskAction
    note: Annotated[str, Field(max_length=1000)] = ""
    due_at: datetime | None = None

    @field_validator("due_at")
    @classmethod
    def aware_due(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            if value.utcoffset() is None:
                raise ValueError("截止时间须包含时区偏移")
            return value.astimezone(UTC)
        return None


class Finding(OutputModel):
    rule_revision_id: int = 0
    kind: str
    object_label: str
    title: str
    severity: Literal["attention", "review"]
    basis: str
    advice: str
    impact: str
    facts: dict[str, str]
    sources: list[SourceReference]
    valid_until: str | None = None


class Branch(OutputModel):
    name: str
    status: Literal["checked", "partial", "not_checked"]
    count: int
    reason: str


class RunSnapshot(OutputModel):
    engine: Literal["local_rules"] = "local_rules"
    model_status: Literal["not_configured"] = "not_configured"
    branches: list[Branch]
    task_ids: list[int]
    sources: list[SourceReference]
    data_as_of: str
    created_candidates: int
    reused_candidates: int


class CheckPreview(OutputModel):
    source_revision: int
    branches: list[Branch]
    findings: list[Finding]
    sources: list[SourceReference]
    valid_until: str | None


class RunOutput(OutputModel):
    id: int
    shop_id: int
    scope: OperationScope
    source_revision: int
    source_status: str
    created_at: str
    valid_until: str | None
    snapshot: RunSnapshot | None


class TaskEventOutput(OutputModel):
    action: str
    from_status: str
    to_status: str
    version: int
    created_at: str
    note: str | None
    due_at: str | None


class TaskOutput(OutputModel):
    id: int
    shop_id: int
    kind: str
    status: str
    source_status: str
    version: int
    snapshot: Finding | None
    note: str
    due_at: str | None
    created_at: str
    owner_id: int
    risk: Literal["R1"] = "R1"
    external_status: Literal["not_submitted"] = "not_submitted"
    history: list[TaskEventOutput]


class TaskPage(OutputModel):
    items: list[TaskOutput]
    has_more: bool
