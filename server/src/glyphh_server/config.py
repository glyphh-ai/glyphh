from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GLYPHH_", env_file=".env", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "postgresql+asyncpg://glyphh:glyphh@localhost:5432/glyphh"
    version: str = "dev"
    log_level: str = "INFO"
    public_url: str = "http://localhost:8080"
    # Signs the values the device sign-in pages carry; 32 characters or more.
    secret_key: str = ""
    # The license's Ed25519 private key: base64 of its raw 32 bytes. Without one outside prod, one is made at start.
    license_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str | None = None
    stripe_price_team: str | None = None
    # Where an invite's link points; the token rides its query. Defaults to {public_url}/join.
    invite_url: str = ""

    @property
    def base_url(self) -> str:
        return self.public_url.rstrip("/")

    @property
    def invite_base(self) -> str:
        return (self.invite_url or f"{self.base_url}/join").rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
