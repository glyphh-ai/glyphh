from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from glyphh_server.bot_settings import BotSettings


class AdaCloudSettings(BaseSettings):
    """Ada Cloud (docs/specs/ada-cloud.md): off by default. Off, nothing of it is reachable (no host routes to it) and
    its worker processes idle without touching the database or Redis. On, requests whose Host is one of ada_hosts
    (comma-separated) reach the Ada API, and the ada and adajobs process groups run the kernel
    (python -m glyphh_ada.worker)."""

    ada_cloud: bool = False
    ada_hosts: str = "ada.glyphh.ai"
    # How long the API waits on a worker's answer: reads, then writes (record_many), before 504 E_TIMEOUT.
    ada_read_timeout: float = Field(10.0, gt=0, le=60)
    ada_write_timeout: float = Field(30.0, gt=0, le=120)
    # Worker processes per machine of a group; 0: one per vCPU.
    ada_workers: int = Field(0, ge=0, le=64)
    # Ada versions (docs/specs/ada-cloud.md, 12.4): where each kernel but the latest stable's is installed
    # (<dir>/<kernel>), and how many worker processes each of those kernels gets per machine of a group.
    ada_kernels_dir: str = "/opt/ada"
    ada_kernel_workers: int = Field(1, ge=1, le=64)
    # The largest file an import takes, in bytes.
    ada_import_bytes: int = Field(200 << 20, ge=1 << 20)
    # The Ada API's address, as the connector hands out its upload and download links.
    ada_url: str = "https://ada.glyphh.ai"
    # Requests past Basic's, Pro's and Team's month, metered (docs/specs/ada-cloud.md, section 7): the price on the
    # ada_requests Billing Meter ($1 per 10,000), on every Basic, Pro and Team subscription, and the meter's event
    # name. Without the price, Checkout answers E_UNAVAILABLE while Ada Cloud is on; without the name, nothing is
    # reported to the meter. scripts/stripe-setup.py makes them and prints these.
    stripe_price_ada: str | None = None
    stripe_meter_ada: str = ""

    @property
    def ada_host_set(self) -> set[str]:
        return {h.strip().lower() for h in self.ada_hosts.split(",") if h.strip()}

    @property
    def ada_base(self) -> str:
        return self.ada_url.rstrip("/")


class LlmSettings(BaseSettings):
    """Glyphh-hosted models (docs/specs/tokens.md): off by default. On (with Ada Cloud on: it is served at the Ada
    hosts, with the same API keys), POST /v1/chat/completions proxies to inference_url, an OpenAI-compatible server
    (vLLM) serving each model under its registry id, and tokens are drawn from the plan's allowance, then charged to
    the org's overage balance. inference_key, when set, is sent to it as a bearer token."""

    llm: bool = False
    inference_url: str = ""
    inference_key: str = ""
    # How long a request waits on the inference server, seconds (a stream, between its chunks).
    inference_timeout: float = Field(300.0, gt=0, le=900)

    @property
    def inference_base(self) -> str:
        return self.inference_url.rstrip("/")


class StaffSettings(BaseSettings):
    """Glyphh's staff (glyphh_server/admin): the verified sign-in emails, comma-separated, that open the staff view on
    the platform. Only through the platform's own sign-in, and every staff request is audited."""

    staff_emails: str = "support@glyphh.ai"

    @property
    def staff_set(self) -> frozenset[str]:
        return frozenset(e.strip().lower() for e in self.staff_emails.split(",") if e.strip())


class TrafficSettings(BaseSettings):
    """The staff view's traffic, pulled each hour by the tick: Glyphh's own sites' from Cloudflare (ops/traffic/pull.py)
    and its public repositories' from GitHub (ops/traffic/github.py). Each token unset, its part says it is not
    connected."""

    # A read-only Cloudflare API token with Zone Analytics on the account's zones.
    cloudflare_api_token: str = ""
    # A GitHub token that may read each repository's traffic (fine-grained: Administration read); the repositories are
    # owner/name, comma-separated.
    github_traffic_token: str = ""
    github_traffic_repos: str = "glyphh-ai/glyphh"


class Settings(AdaCloudSettings, LlmSettings, StaffSettings, TrafficSettings, BotSettings):
    model_config = SettingsConfigDict(env_prefix="GLYPHH_", env_file=".env", extra="ignore", populate_by_name=True)

    env: Literal["dev", "test", "prod"] = "dev"
    # rrotor in the connector (shelved 2026-11-02, back on 2026-11-17): off, the connector neither lists nor calls its
    # runtime, licence and apps tools, and its instructions name Glyphh's account and Ada only. The API's routes stay
    # as they are either way.
    rrotor: bool = True
    database_url: str = "postgresql+asyncpg://glyphh:glyphh@localhost:5432/glyphh"
    # Lets db/reset.py, run by hand, drop every table and make the schema again (development, emergencies). Off by
    # default and never set on deploy: production keeps its data.
    reset_database: bool = False
    # Live signals only (pub/sub): in production Redis runs on the server's own Fly machine, beside the server.
    redis_url: str = "redis://localhost:6379/0"
    version: str = "dev"
    log_level: str = "INFO"
    public_url: str = "http://localhost:8080"
    # The platform, the one web app: every page a browser sees in a flow is there; the server renders nothing.
    platform_url: str = "http://localhost:3000"
    # The platform's own OAuth client, made at every start from these (db/seed_clients.py), so a reset of the
    # database never loses it: the same id and secret as the platform's PLATFORM_CLIENT_ID and PLATFORM_CLIENT_SECRET.
    platform_client_id: str = ""
    platform_client_secret: str = ""
    # Signs the values the device sign-in pages carry; 32 characters or more.
    secret_key: str = ""
    # The Ed25519 private key that signs every licence and licence key: base64 of its raw 32 bytes. Without one outside
    # prod, one is made at start. GLYPHH_LICENSE_KEY is its old name, still read: to rrotor that name is now the
    # customer's key string, so the server's is GLYPHH_LICENSE_SIGNING_KEY.
    license_signing_key: str = Field(
        "",
        validation_alias=AliasChoices("GLYPHH_LICENSE_SIGNING_KEY", "GLYPHH_LICENSE_KEY"),
    )
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_basic: str | None = None
    stripe_price_pro: str | None = None
    stripe_price_team: str | None = None
    # The Glyphh GitHub App: its id, its private key (PEM) and its slug (its install page is under the slug).
    github_app_id: str = ""
    github_app_private_key: str = ""
    github_app_slug: str = ""
    # Where an invite's link points; the token rides its query. Defaults to {public_url}/join.
    invite_url: str = ""
    # Browser origins /mcp accepts besides the server's own, comma-separated (requests without an Origin always pass).
    mcp_origins: str = "https://claude.ai,https://claude.com"

    @field_validator("database_url")
    @classmethod
    def _asyncpg(cls, url: str) -> str:
        """A plain Postgres URL, as Fly's Postgres writes it (`postgres://…?sslmode=…`), made the asyncpg driver's."""
        for plain in ("postgres://", "postgresql://"):
            if url.startswith(plain):
                url = "postgresql+asyncpg://" + url.removeprefix(plain)
        return url.replace("?sslmode=", "?ssl=").replace("&sslmode=", "&ssl=")

    @property
    def hosted(self) -> bool:
        """Glyphh-hosted models are on: GLYPHH_LLM, served at the Ada hosts, so with Ada Cloud on too."""
        return self.llm and self.ada_cloud

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
