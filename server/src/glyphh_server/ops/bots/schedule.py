"""A bot's schedule (docs/specs/bots.md, 9), chosen in plain words, never as cron: off, every hour (on the hour), every
day, weekdays, one weekday each week or one day each month, at a time of day in the person's time zone, with the input
its runs are given. It is kept as it was chosen (bots.schedule); its next run is worked out here, in its zone, and
kept as bots.next_run_at for the minute tick to fire (ops/bots/due.py). A month's day past that month's end is its
last day; a time a clock change skips is the moment after it."""

import calendar
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

Every = Literal["off", "hour", "day", "weekdays", "week", "month"]
DAYS: tuple[str, ...] = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
MONTHS: tuple[str, ...] = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
EVERY_ABOUT: str = (
    "How often it runs: off, hour (every hour, on the hour), day (every day), weekdays (Monday to Friday), week (on "
    "`weekday`) or month (on `day`), at `at` in `timezone`"
)


class Schedule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    every: Every = Field("off", description=EVERY_ABOUT)
    at: str = Field("09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$", description="Its time of day, HH:MM (24 hours)")
    weekday: int = Field(0, ge=0, le=6, description="For every week: 0 Monday to 6 Sunday")
    day: int = Field(1, ge=1, le=31, description="For every month: the day (past the month's end, its last day)")
    timezone: str = Field("UTC", max_length=64, description="The person's time zone (IANA: America/Chicago)")
    input: str = Field(
        "", max_length=20_000, description="What each scheduled run is given; none: the bot's standing task"
    )

    @field_validator("timezone")
    @classmethod
    def _zone(cls, given: str) -> str:
        try:
            ZoneInfo(given)
        except (ZoneInfoNotFoundError, ValueError, OSError) as err:  # a folder of zones (America) is an OSError
            raise ValueError(f"{given!r} is not a time zone (one like America/Chicago)") from err
        return given


def now() -> datetime:
    return datetime.now(UTC)


def _fits(s: Schedule, day: date) -> bool:
    if s.every == "weekdays":
        return day.weekday() < 5
    if s.every == "week":
        return day.weekday() == s.weekday
    if s.every == "month":
        return day.day == min(s.day, calendar.monthrange(day.year, day.month)[1])
    return True


def next_after(s: Schedule, after: datetime) -> datetime | None:
    """Its first run after `after`, in UTC; None when it is off."""
    if s.every == "off":
        return None
    if s.every == "hour":
        return after.astimezone(UTC).replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    zone, (hh, mm) = ZoneInfo(s.timezone), map(int, s.at.split(":"))
    day = after.astimezone(zone).date()
    while True:
        at = datetime.combine(day, time(hh, mm), zone).astimezone(UTC)
        if _fits(s, day) and at > after:
            return at
        day += timedelta(days=1)


def _clock(at: str) -> str:
    hh, mm = at.split(":")
    return f"{int(hh)}:{mm}"


def summary(s: Schedule) -> str:
    """The schedule in plain words: Every day at 9:00."""
    said = {
        "off": "Off",
        "hour": "Every hour",
        "day": f"Every day at {_clock(s.at)}",
        "weekdays": f"Weekdays at {_clock(s.at)}",
        "week": f"Every {DAYS[s.weekday]} at {_clock(s.at)}",
        "month": f"Every month on day {s.day} at {_clock(s.at)}",
    }
    return said[s.every]


def label(s: Schedule, when: datetime | None, at: datetime | None = None) -> str:
    """When its next run is, in its zone: Mon 9:00 (within the week), else Mon 15 Dec 9:00; empty when there is none."""
    if when is None:
        return ""
    local = when.astimezone(ZoneInfo(s.timezone))
    clock = f"{local.hour}:{local.minute:02d}"
    day = DAYS[local.weekday()][:3]
    if when - (at or now()) < timedelta(days=6):
        return f"{day} {clock}"
    return f"{day} {local.day} {MONTHS[local.month - 1]} {clock}"


def shown(bot: Any) -> dict[str, Any]:
    """What a bot's view says of its schedule and where it runs."""
    kept = Schedule(**(bot.schedule or {}))
    return {
        "schedule": kept,
        "schedule_summary": summary(kept),
        "next_run_at": bot.next_run_at,
        "next_run": label(kept, bot.next_run_at),
        "runs_on": bot.runs_on,
    }
