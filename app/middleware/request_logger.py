"""Request logger middleware with detailed metadata and timing."""

import time
import psutil
import os
import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Log every request with comprehensive metadata and performance metrics."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        process = psutil.Process(os.getpid())
        
        # Initial context binding
        structlog.contextvars.bind_contextvars(
            ip_address=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent", "unknown"),
            http_method=request.method,
            endpoint=str(request.url.path),
            api_version="v1", # Default or extract from path
            request_id=getattr(request.state, "correlation_id", "unknown"),
        )

        try:
            response = await call_next(request)
        except Exception as e:
            # In case of unhandled exception, log it
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "REQUEST_FAILED",
                message="request_failed",
                error=str(e),
                status_code=500,
                response_time_ms=duration_ms,
                category="SYSTEM",
            )
            raise e

        duration_ms = int((time.time() - start_time) * 1000)

        # Try to get user info if set by auth middleware
        user_id = getattr(request.state, "user_id", None)
        if not user_id and hasattr(request.state, "user"):
            user_id = getattr(request.state.user, "id", None)

        # Performance metrics
        memory_usage_mb = process.memory_info().rss / (1024 * 1024)
        cpu_usage_percent = process.cpu_percent()

        # Log at appropriate level
        log_fn = logger.info if response.status_code < 400 else logger.warning
        if response.status_code >= 500:
            log_fn = logger.error

        log_fn(
            "API_REQUEST_COMPLETED",
            message="request_processed",
            status_code=response.status_code,
            response_time_ms=duration_ms,
            user_id=str(user_id) if user_id else None,
            operation=f"{request.method}_{request.url.path.replace('/', '_').strip('_')}",
            category="API",
            # Performance
            cpu_usage_percent=cpu_usage_percent,
            memory_usage_mb=round(memory_usage_mb, 2),
            thread_count=process.num_threads(),
            # Additional context placeholders
            tenant_id=getattr(request.state, "tenant_id", "default"),
            auth_method="jwt" if user_id else "anonymous",
            # Tags for filtering
            tags=["api", request.method.lower(), "v1"],
        )

        return response

