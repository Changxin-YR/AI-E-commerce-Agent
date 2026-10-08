from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, PlainSerializer, model_validator

from app.schemas.common import Currency, InputModel, OutputModel

FeeKind = Literal[
    "inbound",
    "outbound",
    "platform",
    "storage",
    "packaging",
    "advertising",
    "refund",
    "tax",
    "other",
]
FEE_LABELS: dict[FeeKind, str] = {
    "inbound": "头程物流",
    "outbound": "尾程物流",
    "platform": "平台费用",
    "storage": "仓储",
    "packaging": "包装",
    "advertising": "广告",
    "refund": "退款损失",
    "tax": "税费",
    "other": "其他及分摊费用",
}
Money = Annotated[Decimal, Field(ge=0, le=100000000, max_digits=13, decimal_places=4)]
DecimalOutput = Annotated[
    Decimal, PlainSerializer(lambda value: format(value, "f"), return_type=str, when_used="json")
]


class FeeInput(InputModel):
    kind: FeeKind
    mode: Literal["fixed", "percent"] = "fixed"
    value: Money | None = None
    basis: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def check_fee(self) -> Self:
        if self.value is not None:
            if not self.basis:
                raise ValueError("已填费用（包括零）必须填写假设依据")
            if self.mode == "percent" and self.value > 100:
                raise ValueError("单项售价费率不能超过 100%")
        return self


class ScenarioInput(InputModel):
    name: str = Field(min_length=1, max_length=80)
    price: Money
    purchase_cost: Money
    basis: str = Field(min_length=1, max_length=500)
    fees: list[FeeInput] = Field(min_length=9, max_length=9)

    @model_validator(mode="after")
    def check_categories(self) -> Self:
        if {fee.kind for fee in self.fees} != set(FEE_LABELS):
            raise ValueError("九类费用必须各出现一次；未知项保留空值")
        return self


class StudyInput(InputModel):
    title: str = Field(min_length=1, max_length=120)
    currency: Currency
    data_identity: Literal["manual_assumption", "synthetic"] = "manual_assumption"
    scenarios: list[ScenarioInput] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def unique_names(self) -> Self:
        if len({item.name for item in self.scenarios}) != len(self.scenarios):
            raise ValueError("方案名称不能重复")
        return self


class SaveStudyInput(StudyInput):
    request_key: UUID


class FeeResult(OutputModel):
    assumption: FeeInput
    amount: DecimalOutput | None


class SensitivityPoint(OutputModel):
    label: str
    price: DecimalOutput
    purchase_cost: DecimalOutput
    known_balance: DecimalOutput
    margin_percent: DecimalOutput | None


class ScenarioResult(OutputModel):
    assumption: ScenarioInput
    purchase_gross: DecimalOutput
    known_fees: DecimalOutput
    known_balance: DecimalOutput
    margin_percent: DecimalOutput | None
    fixed_fees: DecimalOutput
    rate_percent: DecimalOutput
    missing_fees: list[str]
    fees: list[FeeResult]
    break_even_price: DecimalOutput | None
    break_even_reason: str
    sensitivity: list[SensitivityPoint]


class StudyResult(OutputModel):
    input: StudyInput
    rule_version: str
    calculated_at: str
    formula: str
    scope_note: str
    scenarios: list[ScenarioResult]


class SavedStudySummary(OutputModel):
    id: int
    title: str
    currency: str
    data_identity: str
    created_at: str


class SavedStudyOutput(SavedStudySummary):
    result: StudyResult
