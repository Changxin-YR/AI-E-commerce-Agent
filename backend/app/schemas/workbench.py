from typing import Annotated, Literal

from pydantic import Field

from app.schemas.common import InputModel, OutputModel
from app.schemas.imports import DataIdentity, SourceChannel

WorkKind = Literal[
    "operation_task",
    "agent",
    "listing",
    "reply",
    "analysis_todo",
    "operation_run",
    "analysis",
    "overview",
    "authorization",
    "outbound",
]
WorkBucket = Literal["pending", "approval", "failed", "unknown", "stale", "history"]


class WorkQuery(InputModel):
    shop_id: Annotated[int | None, Field(gt=0)] = None
    data_identity: DataIdentity | None = None
    channel: SourceChannel | None = None
    kind: WorkKind | None = None
    bucket: WorkBucket | None = None
    cursor: Annotated[str | None, Field(max_length=600)] = None


class WorkItem(OutputModel):
    kind: WorkKind
    id: int
    target_id: int
    shop_id: int | None
    shop_name: str
    timezone: str
    data_identity: str | None
    channel: str | None
    status: str
    source_status: str
    bucket: WorkBucket
    label: str
    detail: str
    created_at: str
    due_at: str | None
    risk: str
    path: str
    query: dict[str, str]


class WorkPage(OutputModel):
    items: list[WorkItem]
    recent_runs: list[WorkItem]
    counts: dict[str, int]
    next_cursor: str | None
    read_at: str
