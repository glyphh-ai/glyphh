from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GLYPHH_", env_file=".env", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    database_url: str = "postgresql+asyncpg://glyphh:glyphh@localhost:5432/glyphh"
    # Drop every table and make the schema again on each deploy (db/reset.py, Fly's release command): while nothing
    # in the database is kept. Off by default; on only where fly.toml sets GLYPHH_RESET_DATABASE=1.
    reset_database: bool = False
    # Live signals only (pub/sub): in production Redis runs on the server's own Fly machine, beside the server.
    redis_url: str = "redis://localhost:6379/0"
    version: str = "dev"
    log_level: str = "INFO"
    public_url: str = "http://localhost:8080"
    # The platform, the one web app: every page a browser sees in a flow is there; the server renders nothing.
    platform_url: str = "http://localhost:3000"
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
    # The Stripe prices the add-ons sell on, one per mod sold as an add-on.
    stripe_price_ada: str | None = None
    # The Glyphh GitHub App: its id, its private key (PEM) and its slug (its install page is under the slug).
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_app_slug: str = ""
    # Encrypts routine trigger tokens at rest (AES-256-GCM): base64 of 32 random bytes.
    secrets_key: str = ""
    # Where an invite's link points; the token rides its query. Defaults to {public_url}/join.
    invite_url: str = ""
    # Browser origins /mcp accepts besides the server's own, comma-separated (requests without an Origin always pass).
    mcp_origins: str = "https://claude.ai,https://claude.com"
    # Hosted runtimes on Fly: the deploy token, the one app the machines live in, their region, the hosted rrotor
    # image (private: carries the Ada part), and each machine's size. Without a token and an app, hosting is off.
    fly_api_token: str = ""
    fly_app: str = ""
    fly_region: str = "iad"
    fly_image: str = ""
    # The runtimes' public addresses: <machine>.<domain>, a wildcard certificate and DNS record on the app.
    fly_public_domain: str = "glyphh.app"
    fly_cpus: int = 1
    fly_memory_mb: int = 1024
    fly_volume_gb: int = 3
    # A hosted runtime with no run for this long is stopped; a call starts it again.
    runtime_idle_minutes: int = 10

    @field_validator("database_url")
    @classmethod
    def _asyncpg(cls, url: str) -> str:
        """A plain Postgres URL, as Fly's Postgres writes it (`postgres://…?sslmode=…`), made the asyncpg driver's."""
        for plain in ("postgres://", "postgresql://"):
            if url.startswith(plain):
                url = "postgresql+asyncpg://" + url.removeprefix(plain)
        return url.replace("?sslmode=", "?ssl=").replace("&sslmode=", "&ssl=")

    @property
    def base_url(self) -> str:
        return self.public_url.rstrip("/")

    @property
    def platform_base(self) -> str:
        return self.platform_url.rstrip("/")

    @property
    def github_app_configured(self) -> bool:
        return bool(self.github_app_id and self.github_app_private_key and self.github_app_slug)

    @property
    def github_app_install_url(self) -> str:
        return f"https://github.com/apps/{self.github_app_slug}/installations/new"

    @property
    def fly_configured(self) -> bool:
        return bool(self.fly_api_token and self.fly_app and self.fly_image)

    @property
    def mcp_resource(self) -> str:
        """The connector's canonical URI: the resource its access tokens are bound to (RFC 8707)."""
        return f"{self.base_url}/mcp"

    @property
    def mcp_origin_list(self) -> set[str]:
        return {o.strip().rstrip("/") for o in self.mcp_origins.split(",") if o.strip()}

    @property
    def invite_base(self) -> str:
        return (self.invite_url or f"{self.base_url}/join").rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
