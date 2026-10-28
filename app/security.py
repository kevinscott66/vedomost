"""Browser boundary for a deliberately local, unauthenticated demonstration."""

from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse


class LocalBoundaryMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        host = headers.get("host", "").lower()
        try:
            authority = urlsplit("//" + host)
            valid_host = (
                len(headers.getlist("host")) == 1
                and authority.hostname in {"localhost", "127.0.0.1", "::1"}
                and not any(c in host for c in "/@?#\\\t\r\n ")
                and (authority.port is None or 1 <= authority.port <= 65535)
            )
        except ValueError:
            valid_host = False
        error = None
        status = 403
        if not valid_host:
            error, status = "Only explicit loopback hosts are allowed", 400
        elif scope["method"] in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = headers.get("origin")
            if (
                origin is not None and origin.lower() != scope["scheme"] + "://" + host
            ) or headers.get("sec-fetch-site") == "cross-site":
                error = "Cross-origin writes are not allowed"
            elif scope["method"] in {"POST", "PUT", "PATCH"} and (
                headers.get("content-type", "").split(";")[0].strip().lower() != "application/json"
            ):
                error, status = "Content-Type must be application/json", 415

        async def secure_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cache-control", b"no-store"),
                    (
                        b"content-security-policy",
                        (
                            "default-src 'self'; script-src 'self'; style-src 'self'; "
                            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
                            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
                            "form-action 'self'"
                        ).encode(),
                    ),
                ]
            await send(message)

        if error:
            return await JSONResponse({"detail": error}, status_code=status)(
                scope, receive, secure_send
            )
        return await self.app(scope, receive, secure_send)
