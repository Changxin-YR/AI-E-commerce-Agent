from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from app.schemas.common import Currency, InputModel, OutputModel
from app.schemas.imports import DataIdentity, SourceChannel


class RuleScope(InputModel):
    channel: SourceChannel = "generic"
    data_identity: DataIdentity = "user_import"


class RuleNotes(InputModel):
    target_site: Annotated[str, Field(max_length=200)] = ""
    warehouse: Annotated[str, Field(max_length=200)] = ""
    logistics: Annotated[str, Field(max_length=500)] = ""
    brand_voice: Annotated[str, Field(max_length=1000)] = ""
    support_wording: Annotated[str, Field(max_length=1000)] = ""


class RuleValues(InputModel):
    max_age_hours: Annotated[int, Field(ge=1, le=720)] = 24
    min_quantity: Annotated[int, Field(ge=1, le=1000000)] = 1
    max_margin_percent: Annotated[Decimal, Field(ge=-1000, le=100, decimal_places=2)] = Decimal(20)
    advertising_daily_budget: (
        Annotated[Decimal, Field(ge=0, le=100000000, decimal_places=4)] | None
    ) = None
    currency: Currency = "USD"
    notes: RuleNotes = Field(default_factory=RuleNotes)
    basis: Annotated[str, Field(min_length=1, max_length=500)] = "系统初始检查口径"
    automation: Literal["manual_only"] = "manual_only"


class RuleChange(RuleScope):
    expected_version: Annotated[int, Field(ge=0)]
    action: Literal["save", "revoke", "reset", "restore"] = "save"
    values: RuleValues | None = None
    restore_version: Annotated[int, Field(gt=0)] | None = None

    @model_validator(mode="after")
    def valid_action(self) -> Self:
        if (self.action == "save") != (self.values is not None):
            raise ValueError("只有保存操作须提供完整规则")
        if (self.action == "restore") != (self.restore_version is not None):
            raise ValueError("只有恢复操作须指定历史版本")
        if self.values and not self.values.basis.strip():
            raise ValueError("请填写规则依据")
        return self


class RuleRevision(OutputModel):
    version: int
    previous_version: int
    restored_from: int | None
    shop_id: int
    channel: str
    data_identity: str
    action: str
    active: bool
    values: RuleValues
    created_at: str | None
