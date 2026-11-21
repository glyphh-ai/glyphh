"""The voices a bot may speak in (docs/specs/bots.md, 9): Kokoro-82M's, the open text-to-speech model (Apache 2.0)
Glyphh means to serve. Only the choice is kept on the bot for now: no speech is made on the server yet."""

from pydantic import BaseModel

from glyphh_server.errors import Invalid

DEFAULT: str = "af_heart"
ACCENTS: dict[str, tuple[str, str]] = {
    "af": ("American", "female"),
    "am": ("American", "male"),
    "bf": ("British", "female"),
    "bm": ("British", "male"),
}
IDS: tuple[str, ...] = (
    "af_heart", "af_alloy", "af_aoede", "af_bella", "af_jessica", "af_kore", "af_nicole", "af_nova", "af_river",
    "af_sarah", "af_sky", "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", "am_michael", "am_onyx", "am_puck",
    "bf_alice", "bf_emma", "bf_isabella", "bf_lily", "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
)  # fmt: skip


class Voice(BaseModel):
    id: str
    name: str
    accent: str
    gender: str
    default: bool


class Voices(BaseModel):
    voices: list[Voice]
    samples: bool  # whether the server makes speech to hear a voice by (not yet)


def listing() -> Voices:
    shown = []
    for id in IDS:
        accent, gender = ACCENTS[id[:2]]
        shown.append(Voice(id=id, name=id[3:].title(), accent=accent, gender=gender, default=id == DEFAULT))
    return Voices(voices=shown, samples=False)


def voice(id: str) -> str:
    """The voice asked for, or none; a name not on the list is refused."""
    if id and id not in IDS:
        raise Invalid(
            f"A bot speaks in one of the voices GET /v1/bots/voices lists: {id!r} is not one.", reason="voice"
        )
    return id
