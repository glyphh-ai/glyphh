from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GLYPHH_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://glyphh:glyphh@localhost:5432/glyphh"
    version: str = "dev"
    log_level: str = "INFO"
    public_url: str = "http://localhost:8080"
    platform_url: str = ""
    # Other addresses the platform is also opened at, comma separated: locally http://localhost:5173 beside ngrok.
    platform_also: str = ""
    machines_domain: str = "glyphh.ai"
    secret_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    stripe_price_solo: str | None = None
    stripe_price_basic: str | None = None
    stripe_price_pro: str | None = None

    @property
    def platform(self) -> str:
        """Where the platform's pages live (app.glyphh.ai); the server's own address when it serves them too."""
        return (self.platform_url or self.public_url).rstrip("/")

    @property
    def platform_origins(self) -> list[str]:
        """Every address the platform signs in from: its own, then any it is also opened at."""
        also = [o.strip().rstrip("/") for o in self.platform_also.split(",") if o.strip()]
        return [self.platform, *also]


@lru_cache
def get_settings() -> Settings:
    return Settings()
