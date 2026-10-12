"""Every refusal the API sends has one shape: {"error": {"code", "message", "trace_id", ...}}."""

import logging
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.exceptions import HTTPException
from starlette.responses import Response

from glyphh_server.errors import GlyphhError
from glyphh_server.obs.context import current_trace_id
from glyphh_server.obs.logs import fields

log = logging.getLogger("glyphh.api")

_HTTP_CODES: dict[int, str] = {
    400: "E_INVALID",
    401: "E_UNAUTHORIZED",
    403: "E_FORBIDDEN",
    404: "E_NOT_FOUND",
    405: "E_METHOD_NOT_ALLOWED",
    409: "E_CONFLICT",
}


# What a refused sign-in step tells the platform's problem screen, beyond its code: which state to show.
SCREEN_DETAIL: frozenset[str] = frozenset({"reason", "email", "invited", "provider"})


def error_body(code: str, message: str, **detail: Any) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "trace_id": current_trace_id(), **detail}}


def refusal(path: str, platform: str, code: str, message: str, status: int, **detail: Any) -> Response:
    """A person on a sign-in step is sent to the platform's problem page; a program gets JSON."""
    if path.startswith("/auth/"):
        said = {k: str(v) for k, v in detail.items() if k in SCREEN_DETAIL}
        query = urlencode({"code": code, "message": message, "trace": current_trace_id(), **said})
        return RedirectResponse(f"{platform}/problem?{query}", status_code=303)
    return JSONResponse(error_body(code, message, **detail), status_code=status)


def _platform(request: Request) -> str:
    return str(request.app.state.settings.platform)


async def _glyphh_error(request: Request, err: Exception) -> Response:
    assert isinstance(err, GlyphhError)
    log.log(
        logging.ERROR if err.status >= 500 else logging.INFO,
        "refused",
        extra=fields(code=err.code, status=err.status, reason=err.message),
    )
    return refusal(request.url.path, _platform(request), err.code, err.message, err.status, **err.detail)


async def _invalid(request: Request, err: Exception) -> Response:
    assert isinstance(err, RequestValidationError)
    problems = jsonable_encoder(err.errors())
    log.info("refused", extra=fields(code="E_INVALID", status=422, problems=problems))
    return refusal(
        request.url.path, _platform(request), "E_INVALID", "The request is not valid.", 422, problems=problems
    )


async def _http(_: Request, err: Exception) -> JSONResponse:
    assert isinstance(err, HTTPException)
    code = _HTTP_CODES.get(err.status_code, "E_HTTP")
    log.info("refused", extra=fields(code=code, status=err.status_code))
    return JSONResponse(error_body(code, str(err.detail)), status_code=err.status_code, headers=err.headers)


def install(app: FastAPI) -> None:
    app.add_exception_handler(GlyphhError, _glyphh_error)
    app.add_exception_handler(RequestValidationError, _invalid)
    app.add_exception_handler(HTTPException, _http)
