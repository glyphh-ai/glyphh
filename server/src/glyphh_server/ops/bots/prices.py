"""The Claude models a bot runs on, priced as the hosted models are (llm/registry.py's Model), so a bot's tokens are
drawn from the plan's monthly allowance and then charged to the org's balance by the same meter (llm/meter.py). Rates
are Anthropic's own, in US cents per million tokens; allowance_weight is how much of the allowance a token uses next to
the hosted model's (placeholders until Chris sets them, as the hosted list's are)."""

from datetime import date

from pydantic import BaseModel

from glyphh_server.errors import Invalid
from glyphh_server.llm.registry import Model

DEFAULT: str = "claude-opus-5-5"


def _claude(id: str, name: str, input_cents: int, output_cents: int, weight: float) -> Model:
    return Model(id, name, "stable", 1_000_000, input_cents, output_cents, weight, date(2026, 11, 1), name)


CLAUDE: dict[str, Model] = {
    m.id: m
    for m in (
        _claude("claude-opus-5-5", "Claude Opus 5.5", 400, 2000, 8.0),
        _claude("claude-sonnet-5-5", "Claude Sonnet 5.5", 200, 1000, 4.0),
        _claude("claude-haiku-5-5", "Claude Haiku 5.5", 10, 50, 0.2),
    )
}


class BotModel(BaseModel):
    id: str
    name: str
    input_cents_per_mtok: int
    output_cents_per_mtok: int
    default: bool


class BotModels(BaseModel):
    models: list[BotModel]


def listing() -> BotModels:
    return BotModels(
        models=[
            BotModel(
                id=m.id,
                name=m.name,
                input_cents_per_mtok=m.input_cents_per_mtok,
                output_cents_per_mtok=m.output_cents_per_mtok,
                default=m.id == DEFAULT,
            )
            for m in CLAUDE.values()
        ]
    )


def model(id: str) -> Model:
    """The Claude model a bot asks for; a name not on the list is refused."""
    found = CLAUDE.get(id)
    if found is None:
        raise Invalid(f"A bot runs on one of {', '.join(CLAUDE)}: {id!r} is not one.", reason="model")
    return found


def priced(id: str, fallback: str) -> Model:
    """The model that answered (a refusal's fallback may be another), priced; one not on the list as `fallback`."""
    return CLAUDE.get(id) or CLAUDE[fallback]
