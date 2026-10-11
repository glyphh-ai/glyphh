"""Who may do what, and the database's own refusals turned into answers a caller can act on."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import DBAPIError, IntegrityError

from glyphh_server.db.limits import is_limit
from glyphh_server.errors import Conflict, Forbidden, LimitReached
from glyphh_server.ops.auth.principal import Principal

ADMINS: frozenset[str] = frozenset({"org_admin", "super_admin"})


def require_admin(who: Principal) -> None:
    if who.role not in ADMINS:
        raise Forbidden("Only an org admin can do that.", role=who.role)


@contextmanager
def refusals(taken: str) -> Iterator[None]:
    """A seat limit becomes E_LIMIT; a uniqueness clash becomes E_CONFLICT with `taken` as its message."""
    try:
        yield
    except IntegrityError as err:
        raise Conflict(taken) from err
    except DBAPIError as err:
        if is_limit(err):
            raise LimitReached("Your plan's seats are all taken. Upgrade, or free a seat.", limit="seats") from err
        raise
