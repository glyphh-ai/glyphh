"""The platform reads what a consent asks (`GET /auth/consent`) from the browser itself, with the sign-in cookie, so
the answer carries CORS for exactly that: the platform's own origin, with credentials, on that one path. Every other
origin and path gets no CORS header at all. A simple GET needs no preflight, so none is answered."""

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

PATH: str = "/auth/consent"


class ConsentCorsMiddleware:
    def __init__(self, app: ASGIApp, platform_origin: str) -> None:
        self.app = app
        self.platform_origin = platform_origin.rstrip("/")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] != PATH:
            await self.app(scope, receive, send)
            return
        allowed = Headers(scope=scope).get("origin", "").rstrip("/") == self.platform_origin

        async def send_with_cors(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.add_vary_header("Origin")
                if allowed:
                    headers["access-control-allow-origin"] = self.platform_origin
                    headers["access-control-allow-credentials"] = "true"
            await send(message)

        await self.app(scope, receive, send_with_cors)
