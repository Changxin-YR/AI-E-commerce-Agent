from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field, StrictBool, field_validator

from app.schemas.common import InputModel, OutputModel
from app.schemas.operations import OperationScope


class CreateAuthorization(InputModel):
    request_id: UUID
    execution_id: Annotated[int, Field(gt=0)]
    expected_version: Annotated[int, Field(ge=1)]
    skill: Literal["propose_tasks"] = "propose_tasks"
    max_uses: Annotated[int, Field(ge=1, le=20, strict=True)]
    valid_hours: Annotated[int, Field(ge=1, le=168, strict=True)]
    confirmed: StrictBool

    @field_validator("confirmed")
    @classmethod
    def explicit_consent(cls, value: bool) -> bool:
        if not value:
            raise ValueError("需要明确确认预授权范围与恢复边界")
        return value


class RevokeAuthorization(InputModel):
    version: Annotated[int, Field(ge=1)]


class AuthorizationUseOutput(OutputModel):
    id: int
    execution_id: int
    operation_run_id: int
    changes: list[dict[str, Any]]
    reused_count: int
    created_at: str
    reverted_at: str | None


class AuthorizationOutput(OutputModel):
    id: int
    shop_id: int
    version: int
    origin_execution_id: int
    skill: Literal["propose_tasks"] = "propose_tasks"
    risk: Literal["R1"] = "R1"
    scope: OperationScope
    source_revision: int
    candidate_count: int
    max_uses: int
    used_count: int
    status: str
    expires_at: str
    source_valid_until: str | None
    revoked_at: str | None
    created_at: str
    uses: list[AuthorizationUseOutput]


class AuthorizationPage(OutputModel):
    items: list[AuthorizationOutput]
    next_before_id: int | None
