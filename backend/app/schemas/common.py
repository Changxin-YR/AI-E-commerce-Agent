from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("请使用有效的 IANA 时区，例如 Asia/Shanghai") from error
    return value


Timezone = Annotated[str, Field(max_length=64), AfterValidator(validate_timezone)]
Currency = Literal["USD", "CNY", "EUR", "GBP", "JPY", "CAD", "AUD", "HKD", "SGD"]
Market = Annotated[str, Field(pattern=r"^[A-Z]{2}$")]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OutputModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
