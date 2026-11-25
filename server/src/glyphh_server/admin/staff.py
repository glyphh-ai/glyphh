"""Who is Glyphh's staff: a person whose sign-in email is in GLYPHH_STAFF_EMAILS (default support@glyphh.ai). Every
email the server holds for a person was verified by Google or GitHub when they first signed in (ops/auth/signin.py
refuses any other), so the email is the check. The staff view takes only the platform's own sign-in (its OAuth
client): never an install's token or another connector's, so a person's CLI or Claude can't act as staff."""

import uuid

from glyphh_server.config import Settings
from glyphh_server.ops.auth.principal import Principal


def is_staff(settings: Settings, who: Principal) -> bool:
    return bool(who.email) and who.email.strip().lower() in settings.staff_set


def via_platform(settings: Settings, who: Principal) -> bool:
    """Signed in through the platform's own OAuth client (GLYPHH_PLATFORM_CLIENT_ID)."""
    try:
        platform = uuid.UUID(settings.platform_client_id)
    except ValueError:
        return False
    return who.client_id == platform
