from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 是否启用 session 记忆（含 pending clarify 状态机）
    session_memory_enabled: bool = True

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
