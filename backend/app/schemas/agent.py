from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field, StrictBool

from app.schemas.common import InputModel, OutputModel
from app.schemas.operations import OperationScope

Template = Literal["daily", "analysis", "listing", "support", "natural"]
Money = Annotated[Decimal, Field(ge=0, le=10, decimal_places=6)]


class Budget(InputModel):
    max_steps: Annotated[int, Field(ge=1, le=100)] = 12
    max_seconds: Annotated[int, Field(ge=1, le=3600)] = 120
    max_cost_usd: Money = Decimal(0)


class StartAgent(InputModel):
    request_id: UUID
    template: Template = "daily"
    scope: OperationScope
    goal: Annotated[str, Field(max_length=500)] = ""
    product_id: Annotated[int, Field(gt=0)] | None = None
    message_id: Annotated[int, Field(gt=0)] | None = None
    allow_model: StrictBool = False
    budget: Budget = Field(default_factory=Budget)


class AgentAction(InputModel):
    version: Annotated[int, Field(ge=1)]
    action: Literal["advance", "pause", "resume", "cancel", "approve", "reject"]
    budget: Budget | None = None


class SkillDefinition(InputModel):
    name: Annotated[str, Field(min_length=1)]
    version: Annotated[str, Field(min_length=1)]
    purpose: Annotated[str, Field(min_length=1)]
    input_schema: dict[str, Any]
    input_sources: Annotated[list[str], Field(min_length=1)]
    output_schema: dict[str, Any]
    permissions: Annotated[list[str], Field(min_length=1)]
    tools: Annotated[list[str], Field(min_length=1)]
    read_scope: Annotated[str, Field(min_length=1)]
    write_scope: Annotated[str, Field(min_length=1)]
    risk: Literal["R0", "R1", "R2", "R3"]
    side_effects: StrictBool
    preconditions: Annotated[list[str], Field(min_length=1)]
    idempotency: Annotated[str, Field(min_length=1)]
    max_attempts: Annotated[int, Field(ge=1, le=3)]
    failure_policy: Annotated[str, Field(min_length=1)]
    confirmation: Annotated[str, Field(min_length=1)]


class StepOutput(OutputModel):
    id: int
    node: str
    skill: str
    skill_version: str
    status: str
    reason: str
    next_node: str
    input: dict[str, Any] | None
    output: dict[str, Any] | None
    duration_ms: int
    created_at: str


class AgentOutput(OutputModel):
    id: int
    shop_id: int
    template: str
    status: str
    reason: str
    version: int
    next_node: str
    source_status: str
    source_revision: int
    input: StartAgent | None
    result: dict[str, Any] | None
    steps_used: int
    elapsed_ms: int
    budget: Budget
    spent_usd: Decimal
    reserved_usd: Decimal
    model_status: str
    created_at: str
    steps: list[StepOutput]
    external_status: Literal["not_submitted"] = "not_submitted"


class ModelDecision(InputModel):
    intent: Literal["daily", "analysis", "listing", "support", "blocked"]


class ModelStatus(OutputModel):
    status: str
    provider: str
    model: str
    reason: str
