"""A candidate's Greenhouse record as the `greenhouse` model reads it. UNPROVEN: written from Greenhouse's Harvest
v3 reference (harvestdocs.greenhouse.io: the candidate and the application objects) and never run against a real
Greenhouse account. Only what those objects really carry is read: where the application came from (`source_id`),
whether someone referred it (`referrer_id`), whether it is a prospect, the screening questions and how much was
answered (`answers`), whether it names a location, the contact details the candidate record holds (how many email
addresses, phone numbers, websites and social profiles), whether it names a company, a title and a time zone, its
tags, and whether the candidate record was made with this application or was there before. Harvest gives no IP
address, no browser, no time taken to fill in the form and no duplicate marker, so none of those is here.

It names no flags: nothing says yet which of these marks a person who is not real. The model starts with no
precedents and learns only from the person's answers."""

from datetime import datetime
from typing import Any

NEW: int = 300  # seconds: a candidate record made this close to the application was made by it


def _n(said: Any, most: int = 10) -> int:
    return min(most, len(said)) if isinstance(said, list) else 0


def _at(said: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(said).replace("Z", "+00:00"))
    except ValueError:
        return None


def read(candidate: dict[str, Any], application: dict[str, Any]) -> dict[str, Any]:
    answers = [a for a in (application.get("answers") or []) if isinstance(a, dict)]
    said = [str(a.get("answer") or "").strip() for a in answers]
    made, applied = _at(candidate.get("created_at")), _at(application.get("created_at"))
    new = "unknown" if not (made and applied) else "yes" if abs((applied - made).total_seconds()) <= NEW else "no"
    return {
        "source": str(application.get("source_id") or "none"),
        "referred": "yes" if application.get("referrer_id") else "no",
        "prospect": "yes" if application.get("prospect") else "no",
        "located": "yes" if application.get("location_address") else "no",
        "questions": _n(answers, 40),
        "answered": min(40, sum(1 for s in said if s)),
        "answer_words": min(1000, sum(len(s.split()) for s in said)),
        "emails": _n(candidate.get("email_addresses")),
        "phones": _n(candidate.get("phone_numbers")),
        "websites": _n(candidate.get("website_addresses")),
        "socials": _n(candidate.get("social_media_addresses")),
        "company": "yes" if candidate.get("company") else "no",
        "title": "yes" if candidate.get("title") else "no",
        "time_zone": "yes" if candidate.get("time_zone") else "no",
        "tags": sorted(str(t).lower() for t in (candidate.get("tags") or []))[:20] or ["none"],
        "new_candidate": new,
    }


def found(signals: dict[str, Any]) -> list[str]:
    """What the record says, in a sentence: told to the person, never a judgement."""
    came = "referred" if signals["referred"] == "yes" else f"source {signals['source']}"
    return [
        f"{came}; {signals['answered']} of {signals['questions']} questions answered; "
        f"{signals['emails']} email, {signals['phones']} phone, {signals['websites'] + signals['socials']} links"
    ]
