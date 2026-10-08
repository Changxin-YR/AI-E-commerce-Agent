from typing import Literal

from pydantic import BaseModel, Field, SecretStr

from app.schemas.common import Currency, InputModel, Market, OutputModel, Timezone


class LoginInput(BaseModel):
    # Password whitespace is significant, so do not inherit str_strip_whitespace.
    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=128)


class AccountInput(BaseModel):
    username: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{2,63}$")
    password: SecretStr = Field(min_length=12, max_length=128)


class SessionOutput(BaseModel):
    user_id: int
    username: str
    csrf_token: str


class ProfileInput(InputModel):
    display_name: str = Field(min_length=1, max_length=80)
    target_market: Market
    business_model: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=1, max_length=120)
    currency: Currency
    timezone: Timezone
    language: Literal["zh-CN", "en", "ja", "de", "fr", "es"]
    version: int = Field(ge=0)


class ProfileOutput(ProfileInput, OutputModel):
    pass


class ShopInput(InputModel):
    code: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{1,39}$")
    name: str = Field(min_length=1, max_length=80)
    platform: Literal["manual", "shopify", "amazon", "other"]
    market: Market
    currency: Currency
    timezone: Timezone


class ShopOutput(ShopInput, OutputModel):
    id: int
    connection_status: Literal["file_only"] = "file_only"


class OnboardingOutput(BaseModel):
    profile_complete: bool
    shop_count: int
    data_mode: Literal["file_import"] = "file_import"
    next_step: Literal["profile", "shop", "import"]
