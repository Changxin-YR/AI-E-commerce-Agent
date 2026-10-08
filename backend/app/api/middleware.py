from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, Request, Response

from app.api.errors import error_response
from app.core.config import Settings


def register_request_middleware(app: FastAPI, settings: Settings) -> None:
    @app.middleware("http")
    async def protect_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request.state.request_id = uuid4().hex
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin is not None and origin not in settings.trusted_origins:
                return error_response(request, "origin_rejected", "请求来源未获允许", 403)
            # A custom header makes login/logout unavailable to cross-origin HTML forms.
            if request.headers.get("X-SoloOps-Client") != "web":
                return error_response(request, "client_rejected", "缺少请求来源标识", 403)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response
