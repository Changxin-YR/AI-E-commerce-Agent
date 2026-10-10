from datetime import UTC, datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StrictBool, field_validator, model_validator

from app.schemas.analytics import AnalysisInput, SourceReference
from app.schemas.common import InputModel, OutputModel
from app.schemas.imports import DataIdentity, SourceChannel


class OperationScope(AnalysisInput):
    cost_mode: Literal["current_estimate"] = "current_estimate"
    rule_revision_id: Annotated[int, Field(ge=0)] = 0
    intent: Literal["low_margin"] = "low_margin"
    channel: SourceChannel = "generic"
    max_age_hours: Annotated[int, Field(ge=1, le=720)] = 24


class RunInput(InputModel):
    request_id: UUID
    scope: OperationScope
    expected_preview_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] | None = None


class TaskQuery(InputModel):
    data_identity: DataIdentity = "user_import"
    channel: SourceChannel = "generic"
    offset: Annotated[int, Field(ge=0, le=1000000)] = 0


TaskAction = Literal[
    "approve",
    "reject",
    "ignore",
    "defer",
    "complete",
    "reopen",
    "edit",
    "record_evidence",
    "wait_source",
    "recheck",
]
BusinessState = Literal[
    "pending_review",
    "checked_pending",
    "evidence_recorded",
    "awaiting_source",
    "resolved",
    "still_anomalous",
    "ignored",
    "cleared",
]


class TaskEvidenceInput(InputModel):
    description: Annotated[str, Field(min_length=1, max_length=1000)]
    evidence_ref: Annotated[str, Field(min_length=1, max_length=500)]
    occurred_at: datetime
    confirmed: StrictBool

    @field_validator("occurred_at")
    @classmethod
    def aware_occurred(cls, value: datetime) -> datetime:
        if value.utcoffset() is None or not 2000 <= value.year <= 2100:
            raise ValueError("操作时间须包含时区且在2000—2100年之间")
        return value.astimezone(UTC)

    @field_validator("confirmed")
    @classmethod
    def require_confirmation(cls, value: bool) -> bool:
        if not value:
            raise ValueError("请确认这是卖家自报的操作记录")
        return value


class TaskEvidence(OutputModel):
    description: str
    evidence_ref: str
    occurred_at: str
    recorded_at: str
    recorded_by: int
    provenance: Literal["seller_reported"] = "seller_reported"


class TaskRecheck(OutputModel):
    state: Literal["awaiting_source", "resolved", "still_anomalous"]
    reason: str
    checked_at: str
    source_revision: int
    valid_until: str | None = None
    facts: dict[str, str] = Field(default_factory=dict)
    sources: list[SourceReference] = Field(default_factory=list)


class TaskReview(OutputModel):
    state: BusinessState
    evidence: TaskEvidence | None = None
    recheck: TaskRecheck | None = None


class TaskInput(InputModel):
    version: Annotated[int, Field(ge=1)]
    action: TaskAction
    note: Annotated[str, Field(max_length=1000)] = ""
    due_at: datetime | None = None
    evidence: TaskEvidenceInput | None = None

    @model_validator(mode="after")
    def evidence_action(self) -> Self:
        if (self.action == "record_evidence") != (self.evidence is not None):
            raise ValueError("登记操作证据须提供凭据，其他操作不接受凭据字段")
        return self

    @field_validator("due_at")
    @classmethod
    def aware_due(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            if value.utcoffset() is None:
                raise ValueError("截止时间须包含时区偏移")
            return value.astimezone(UTC)
        return None


class Finding(OutputModel):
    scope: OperationScope | None = None
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


class OperationContext(OutputModel):
    preview: CheckPreview
    preview_hash: str


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
    review: TaskReview | None = None


class TaskDestination(OutputModel):
    label: str
    path: Literal["/imports", "/inventory", "/analytics", "/listings", "/support"]
    query: dict[str, str]


class TaskOutput(OutputModel):
    id: int
    shop_id: int
    data_identity: DataIdentity
    channel: SourceChannel
    destinations: list[TaskDestination] = Field(default_factory=list)
    kind: str
    status: str
    source_status: str
    business_state: BusinessState = "pending_review"
    review: TaskReview | None = None
    review_current: bool = False
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
