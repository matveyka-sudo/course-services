import functools
from typing import final

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """Название и описание приложения."""

    title: str = "Course Service"
    description: str = "Course Service description"
    summary: str = "Course Service summary"
    version: str = "0.1.0"


@final
class Settings(BaseSettings):
    """Общие настройки сервиса."""

    app: AppSettings = Field(default_factory=AppSettings)
    model_config = SettingsConfigDict(
        extra="allow",
        env_file=".env",
        env_nested_delimiter="__",
        env_file_encoding="utf-8",
    )


@functools.lru_cache
def get_settings() -> Settings:
    """Получить настройки приложения."""

    return Settings()
