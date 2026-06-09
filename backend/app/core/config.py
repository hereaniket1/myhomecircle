from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "myhomecircle"
    app_version: str = "0.1.0"
    database_url: str = Field(
        default="postgresql+psycopg://myhomecircle:myhomecircle@localhost:5432/myhomecircle"
    )
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
