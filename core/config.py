from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = Field(..., min_length=1)
    manager_chat_id: int | None = None

    mcp_server_url: str = Field(default="https://mcp.silpo.ua/mcp")
    mcp_api_key: str | None = None
    mcp_protocol_version: str = "2025-06-18"
    mcp_request_timeout_seconds: float = 60.0
    delivery_address: str = "Київ, вул. Богдана Хмельницького, 1"
    delivery_type_preference: str = ""

    database_url: str = "postgresql+asyncpg://localhost:5432/silpo_home"

    scan_interval_hours: int = 6
    min_discount_percent: float = 50.0
    max_posts_per_scan: int = 10
    deal_default_deadline_days: int = 3

    @field_validator("manager_chat_id", mode="before")
    @classmethod
    def empty_int_to_none(cls, value):
        if value == "":
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
