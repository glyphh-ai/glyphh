"""A request's body within its bound before anything parses it: 1 MB, record_many 5 MB, an import whose file rides in
its body 5 MB of file (base64 makes it a third more) (413 E_TOO_LARGE)."""

from fastapi import Request

from glyphh_ada import limits
from glyphh_server.errors import TooLarge

IMPORT_BODY_MAX: int = limits.IMPORT_BODY_MAX * 4 // 3 + (64 << 10)


def _most(path: str) -> int:
    if path.endswith("/record_many"):
        return limits.RECORD_MANY_BODY_MAX
    return IMPORT_BODY_MAX if path.endswith("/imports") else limits.BODY_MAX


async def bounded(request: Request) -> None:
    most = _most(request.url.path)
    declared = request.headers.get("content-length", "")
    if (declared.isdigit() and int(declared) > most) or len(await request.body()) > most:
        raise TooLarge(f"A request's body is at most {most} bytes here.", max=most)
