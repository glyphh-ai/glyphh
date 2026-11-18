from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """What is left of the Glyphh server after its products were retired (2026-11-18): the staff's sign-in through the
    platform, the staff view, Stripe's webhook and the health check. Every setting is read from the environment
    (prefix GLYPHH_, or .env)."""

    model_config = SettingsConfigDict(env_prefix="GLYPHH_", env_file=".env", extra="ignore", populate_by_name=True)

    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "postgresql+asyncpg://glyphh:glyphh@localhost:5432/glyphh"
    # Lets db/reset.py, run by hand, drop every table and make the schema again (development, emergencies). Off by
    # default and never set on deploy: production keeps its data.
    reset_database: bool = False
    # The request metrics, the tick's heartbeat and the ops events on their way to Postgres: nothing kept.
    redis_url: str = "redis://localhost:6379/0"
    version: str = "dev"
    log_level: str = "INFO"
    public_url: str = "http://localhost:8080"
    # The platform, the one web app: every page a browser sees in a flow is there; the server renders nothing.
    platform_url: str = "http://localhost:3000"
    # The platform's own OAuth client, made at every start from these (db/seed_clients.py), so a reset of the
    # database never loses it: the same id and secret as the platform's PLATFORM_CLIENT_ID and PLATFORM_CLIENT_SECRET.
    # The only client that is issued tokens.
    platform_client_id: str = ""
    platform_client_secret: str = ""
    # Signs the values the sign-in steps carry; 32 characters or more.
    secret_key: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    # Stripe's webhook still records cancellations and last payments on their orgs (ops/billing/webhook.py): the key
    # reads the subscription an event names, the secret checks the event's signature.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # Glyphh's staff (admin/staff.py): the verified sign-in emails, comma-separated. Nobody else signs in.
    staff_emails: str = "support@glyphh.ai"
    # A read-only Cloudflare API token with Zone Analytics on the account's zones: the staff view's traffic, pulled
    # each hour by the tick (ops/traffic/pull.py). Unset, the page says it is not connected.
    cloudflare_api_token: str = ""

    @field_validator("database_url")
    @classmethod
    def _asyncpg(cls, url: str) -> str:
        """A plain Postgres URL, as Fly's Postgres writes it (`postgres://…?sslmode=…`), made the asyncpg driver's."""
        for plain in ("postgres://", "postgresql://"):
            if url.startswith(plain):
                url = "postgresql+asyncpg://" + url.removeprefix(plain)
        return url.replace("?sslmode=", "?ssl=").replace("&sslmode=", "&ssl=")

    @property
    def staff_set(self) -> frozenset[str]:
        return frozenset(e.strip().lower() for e in self.staff_emails.split(",") if e.strip())

    @property
    def base_url(self) -> str:
        return self.public_url.rstrip("/")

    @property
    def platform_base(self) -> str:
        return self.platform_url.rstrip("/")

    @property
    def token_resource(self) -> str:
        """The resource every access token is bound to (RFC 8707). It is still the retired connector's address,
        `/mcp`: each sign-in the database holds was granted for it, and they go on working."""
        return f"{self.base_url}/mcp"


@lru_cache
def get_settings() -> Settings:
    return Settings()
