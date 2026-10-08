from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SOLOOPS_", env_file=".env", extra="ignore")

    database_url: SecretStr
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
