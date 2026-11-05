from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class AppSettings(BaseSettings):
    title: str = "Course Service"
    description: str = "API учебных курсов"
    summary: str = "Course Service"
    version: str = "1.0.0"


class DatabaseSettings(BaseSettings):
    dsn: SecretStr = SecretStr("postgresql://postgres:postgres@localhost:5432/courses")
    min_pool_size: int = Field(default=1, ge=1)
    max_pool_size: int = Field(default=10, ge=1)
    command_timeout: float = Field(default=10, gt=0)

    @model_validator(mode="after")
    def validate_pool(self) -> Self:
        if self.min_pool_size > self.max_pool_size:
            raise ValueError("min_pool_size exceeds max_pool_size")
        return self


class AuthSettings(BaseSettings):
    secret: SecretStr = SecretStr("")
    issuer: str | None = None
    audience: str | None = None


class CheckerSettings(BaseSettings):
    url: str | None = None
    timeout: float = Field(default=5, gt=0)
    concurrency: int = Field(default=5, ge=1)


class Settings(BaseSettings):
    app: AppSettings = Field(default_factory=AppSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    checker: CheckerSettings = Field(default_factory=CheckerSettings)
    cors_origins: list[str] = Field(default_factory=list)
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    log_level: str = "INFO"
    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=ROOT / ".env",
        env_nested_delimiter="__",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
