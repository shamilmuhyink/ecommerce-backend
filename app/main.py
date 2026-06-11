"""FastAPI application factory, lifespan, and middleware registration."""

from contextlib import asynccontextmanager
import os

import structlog
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AppException
from app.core.logging import configure_logging
from app.core.redis import redis_client
from app.middleware.correlation_id import CorrelationIdMiddleware
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.request_logger import RequestLoggerMiddleware

settings = get_settings()
logger = structlog.get_logger(__name__)

configure_logging(settings.APP_ENV)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    """Application lifespan: startup and shutdown hooks."""
    logger.info("application_starting", env=settings.APP_ENV)
    yield
    # Shutdown: close Redis connection pool
    await redis_client.close()
    logger.info("application_shutdown_complete")


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    redirect_slashes=False,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Mount static files for development uploads
if settings.APP_ENV == "development":
    os.makedirs("uploads/products", exist_ok=True)
    app.mount("/static", StaticFiles(directory="uploads"), name="static")

# ---------------------------------------------------------------------------
# Middleware registration (order matters — LAST added = OUTERMOST = first to run)
# ---------------------------------------------------------------------------

if settings.APP_ENV not in ("testing", "development"):
    app.add_middleware(RateLimiterMiddleware, limit=100, window=60)

app.add_middleware(RequestLoggerMiddleware)
app.add_middleware(CorrelationIdMiddleware)

# CORS — MUST be outermost so it handles OPTIONS preflight and adds headers
# to ALL responses, including errors from inner middleware.
cors_origins: list[str] = [str(o) for o in settings.ALLOWED_ORIGINS]
if not cors_origins and settings.APP_ENV == "development":
    cors_origins = ["http://localhost:4200", "http://127.0.0.1:4200"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include API routers
app.include_router(api_router, prefix="/api/v1")


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handle all AppException subclasses with standard error envelope."""
    from app.schemas.common import ApiError, ApiResponse

    correlation_id = getattr(request.state, "correlation_id", "unknown")
    errors = [ApiError(code=exc.code, field=None, message=exc.message)]
    if exc.details:
        for field, msg in exc.details.items():
            errors.append(ApiError(code=exc.code, field=str(field), message=str(msg)))

    response = ApiResponse.error(message=exc.message, errors=errors)
    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(),
        headers={"X-Request-ID": correlation_id},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled exceptions — log full trace, return safe message."""
    from app.schemas.common import ApiError, ApiResponse

    correlation_id = getattr(request.state, "correlation_id", "unknown")
    logger.exception(
        "unhandled_exception",
        exc_info=exc,
        request_id=correlation_id,
        path=request.url.path,
    )
    response = ApiResponse.error(
        message="An unexpected error occurred. Our team has been notified.",
        errors=[ApiError(code="INTERNAL_SERVER_ERROR", field=None, message=str(exc))],
    )
    return JSONResponse(
        status_code=500,
        content=response.model_dump(),
        headers={"X-Request-ID": correlation_id},
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint for load balancer and container orchestration."""
    from app.schemas.common import ApiResponse

    response = ApiResponse.success(
        data={"status": "ok", "env": settings.APP_ENV},
        message="Service is healthy",
    )
    return response.model_dump()
