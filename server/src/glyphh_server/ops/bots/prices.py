"""The Claude models a bot runs on, priced as the hosted models are (llm/registry.py's Model), so a bot's tokens are
drawn from the plan's monthly allowance and then charged to the org's balance by the same meter (llm/meter.py). Every
bot token is charged, on whichever key the org chose: on Glyphh's key, Anthropic's rate and Glyphh's markup; on the
org's own key (it pays Anthropic itself), the markup alone. Rates are in US cents per million tokens; allowance_weight
is how much of the allowance a token uses next to the hosted model's (placeholders until Chris sets them, as the
hosted list's are)."""

from dataclasses import replace
from datetime import date

from pydantic import BaseModel, Field

from glyphh_server.errors import Invalid
from glyphh_server.llm.registry import Model
from glyphh_server.ops.bots import access

DEFAULT: str = "claude-opus-5-5"
MARKUP_PCT: int = 20  # Glyphh's markup on Anthropic's rate, on either key


def _claude(id: str, name: str, input_cents: int, output_cents: int, weight: float) -> Model:
    return Model(id, name, "stable", 1_000_000, input_cents, output_cents, weight, date(2026, 11, 1), name)


CLAUDE: dict[str, Model] = {  # Anthropic's own rates
    m.id: m
    for m in (
        _claude("claude-opus-5-5", "Claude Opus 5.5", 400, 2000, 8.0),
        _claude("claude-sonnet-5-5", "Claude Sonnet 5.5", 200, 1000, 4.0),
        _claude("claude-haiku-5-5", "Claude Haiku 5.5", 10, 50, 0.2),
    )
}


def _of(cents: int, own_key: bool) -> int:
    return cents * (MARKUP_PCT if own_key else 100 + MARKUP_PCT) // 100


class BotModel(BaseModel):
    id: str
    name: str
    input_cents_per_mtok: int  # on Glyphh's key: Anthropic's rate and the markup
    output_cents_per_mtok: int
    own_key_input_cents_per_mtok: int  # on the org's own key: the markup alone
    own_key_output_cents_per_mtok: int
    default: bool


class BotModels(BaseModel):
    models: list[BotModel]
    markup_pct: int
    efforts: list[str] = Field(description="The efforts a bot may be set to (every model here takes each)")
    default_effort: str


def listing() -> BotModels:
    shown = [
        BotModel(
            id=m.id,
            name=m.name,
            input_cents_per_mtok=_of(m.input_cents_per_mtok, False),
            output_cents_per_mtok=_of(m.output_cents_per_mtok, False),
            own_key_input_cents_per_mtok=_of(m.input_cents_per_mtok, True),
            own_key_output_cents_per_mtok=_of(m.output_cents_per_mtok, True),
            default=m.id == DEFAULT,
        )
        for m in CLAUDE.values()
    ]
    return BotModels(
        models=shown, markup_pct=MARKUP_PCT, efforts=list(access.EFFORTS), default_effort=access.DEFAULT_EFFORT
    )


def model(id: str) -> Model:
    """The Claude model a bot asks for, at Anthropic's rate; a name not on the list is refused."""
    found = CLAUDE.get(id)
    if found is None:
        raise Invalid(f"A bot runs on one of {', '.join(CLAUDE)}: {id!r} is not one.", reason="model")
    return found


def charged(id: str, own_key: bool) -> Model:
    """The model as a bot's tokens are charged on the key it ran on."""
    m = model(id)
    return replace(
        m,
        input_cents_per_mtok=_of(m.input_cents_per_mtok, own_key),
        output_cents_per_mtok=_of(m.output_cents_per_mtok, own_key),
    )
