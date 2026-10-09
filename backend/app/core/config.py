from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SOLOOPS_", env_file=".env", extra="ignore")

    database_url: SecretStr
    scheduler_enabled: bool = True
    outbound_enabled: bool = False
    outbound_api_key: SecretStr | None = None
    outbound_owner_id: int | None = None
    outbound_shop_id: int | None = None
    outbound_sender: str = ""
    outbound_test_recipient: str = ""
    outbound_domain_id: UUID | None = None
    model_enabled: bool = False
    model_provider: Literal["openai_responses", "dashscope_chat"] = "openai_responses"
    model_api_key: SecretStr | None = None
    model_name: str = ""
    model_input_usd_per_million: Decimal | None = Field(default=None, gt=0, le=1000)
    model_output_usd_per_million: Decimal | None = Field(default=None, gt=0, le=1000)
    model_cost_note: str = Field(default="按部署费率估算，以供应商账单为准", max_length=240)
    cookie_secure: bool = False
    session_hours: int = Field(default=12, ge=1, le=168)
    trusted_hosts: list[str] = ["localhost", "127.0.0.1"]
    trusted_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    @field_validator("database_url")
    @classmethod
    def require_mysql(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith("mysql+pymysql://"):
            raise ValueError("SoloOps requires a mysql+pymysql connection URL")
        return value
