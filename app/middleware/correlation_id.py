"""Correlation ID middleware — binds request ID to structlog context."""

import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Ensure every request has a correlation ID for traceability.

    If the client sends X-Correlation-ID, it is reused. Otherwise a new
    UUID is generated. The ID is bound to structlog contextvars so that
    all log entries within the request include it.
    """

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Add to request state (accessible by exception handlers)
        request.state.correlation_id = correlation_id

        # Bind to structlog context for all downstream log calls
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        response: Response = await call_next(request)

        # Add to response headers
        response.headers["X-Correlation-ID"] = correlation_id
        return response
