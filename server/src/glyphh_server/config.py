from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GLYPHH_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://glyphh:glyphh@localhost:5432/glyphh"
    version: str = "dev"
    stripe_price_solo: str | None = None
    stripe_price_basic: str | None = None
    stripe_price_pro: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
