"""Every refusal the API sends has one shape: {"error": {"code", "message", "trace_id", ...}}. A person on a sign-in
page sees the same refusal as a plain page instead."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.responses import Response

from glyphh_server.api.pages import page
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

PAGES: tuple[str, ...] = ("/auth/", "/v1/device", "/billing/", "/oauth/authorize")
# Pages on an address whose other methods are the API's.
GET_PAGES: tuple[str, ...] = ("/v1/github/install", "/v1/github/callback")


def is_page(method: str, path: str) -> bool:
    if method == "GET" and path in GET_PAGES:
        return True
    return path.startswith(PAGES) and path not in ("/v1/device/code", "/v1/device/token")


def error_body(code: str, message: str, **detail: Any) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "trace_id": current_trace_id(), **detail}}


def refusal(method: str, path: str, code: str, message: str, status: int, **detail: Any) -> Response:
    """A person on a page gets a page; a model gets JSON."""
    if is_page(method, path):
        return page("That didn't work", message, f"Code {code}, trace {current_trace_id()}.", status=status)
    return JSONResponse(error_body(code, message, **detail), status_code=status)


async def _glyphh_error(request: Request, err: Exception) -> Response:
    assert isinstance(err, GlyphhError)
    log.log(
        logging.ERROR if err.status >= 500 else logging.INFO,
        "refused",
        extra=fields(code=err.code, status=err.status, reason=err.message),
    )
    return refusal(request.method, request.url.path, err.code, err.message, err.status, **err.detail)


async def _invalid(request: Request, err: Exception) -> Response:
    assert isinstance(err, RequestValidationError)
    problems = jsonable_encoder(err.errors())
    log.info("refused", extra=fields(code="E_INVALID", status=422, problems=problems))
    return refusal(request.method, request.url.path, "E_INVALID", "The request is not valid.", 422, problems=problems)


async def _http(request: Request, err: Exception) -> Response:
    assert isinstance(err, HTTPException)
    code = _HTTP_CODES.get(err.status_code, "E_HTTP")
    log.info("refused", extra=fields(code=code, status=err.status_code))
    return JSONResponse(error_body(code, str(err.detail)), status_code=err.status_code, headers=err.headers)


def install(app: FastAPI) -> None:
    app.add_exception_handler(GlyphhError, _glyphh_error)
    app.add_exception_handler(RequestValidationError, _invalid)
    app.add_exception_handler(HTTPException, _http)
