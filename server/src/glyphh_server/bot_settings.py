from pydantic_settings import BaseSettings


class BotSettings(BaseSettings):
    """Hosted bots (docs/specs/bots.md). Claude runs them with anthropic_api_key; unset, starting a run answers 503
    E_UNAVAILABLE (reason anthropic_off).
    Connections are Pipedream Connect accounts (one Pipedream project, its OAuth client); unset, the connections
    routes answer 503 E_UNAVAILABLE (reason pipedream_off) and bots run with Ada and no other tools."""

    anthropic_api_key: str = ""
    pipedream_client_id: str = ""
    pipedream_client_secret: str = ""
    pipedream_project_id: str = ""
    pipedream_environment: str = "production"
    # Runs at once on one machine; the rest wait their turn.
    bot_runs_at_once: int = 4

    @property
    def pipedream_on(self) -> bool:
        return bool(self.pipedream_client_id and self.pipedream_client_secret and self.pipedream_project_id)
