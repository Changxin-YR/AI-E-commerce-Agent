from decimal import Decimal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SOLOOPS_", env_file=".env", extra="ignore")

    database_url: SecretStr
    model_enabled: bool = False
    model_api_key: SecretStr | None = None
    model_name: str = ""
    model_input_usd_per_million: Decimal | None = Field(default=None, gt=0, le=1000)
    model_output_usd_per_million: Decimal | None = Field(default=None, gt=0, le=1000)
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
