"""Who may do what, and the database's own refusals turned into answers a caller can act on."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError

from glyphh_server.errors import Conflict, Forbidden
from glyphh_server.ops.auth.principal import Principal


def require_admin(who: Principal) -> None:
    if who.role != "admin":
        raise Forbidden("Only your org's admin can do that.", role=who.role)


@contextmanager
def taken(message: str, **detail: object) -> Iterator[None]:
    """A uniqueness clash becomes E_CONFLICT with this message."""
    try:
        yield
    except IntegrityError as err:
        raise Conflict(message, **detail) from err
