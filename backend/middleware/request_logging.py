import logging
import sys
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.request")

_configured = False


def configure_app_request_logging() -> None:
    """Attach a stderr handler so lines show under Uvicorn (root is often WARNING)."""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:\t%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    _configured = True


class AuthRequestLogMiddleware(BaseHTTPMiddleware):
    """Log method, path, status, client IP, request id, and authenticated user (if any)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get("x-request-id") or request.headers.get("X-Request-ID")
        request_id = (incoming or "").strip() or uuid.uuid4().hex[:12]
        request.state.request_id = request_id

        response = await call_next(request)

        user_id = getattr(request.state, "user_id", None)
        user_email = getattr(request.state, "user_email", None)
        user_part = user_email or user_id or "-"

        client = request.client.host if request.client else "-"

        logger.info(
            'rid=%s client=%s "%s %s" %s user=%s',
            request_id,
            client,
            request.method,
            request.url.path,
            response.status_code,
            user_part,
        )

        response.headers["X-Request-ID"] = request_id
        return response
