import logging
import os
import socket
import sys
import threading
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any, MutableMapping

import structlog
from app.core.config import get_settings


def add_app_context(
    logger: Any,
    method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Add application context to every log entry.

    In production, includes comprehensive service and infrastructure metadata
    for log aggregation, tracing, and incident response.
    In development, keeps it minimal for readability.
    """
    settings = get_settings()
    event_dict["service"] = settings.APP_NAME.lower().replace(" ", "-")
    event_dict["environment"] = settings.APP_ENV

    if settings.APP_ENV != "development":
        event_dict["version"] = os.getenv("APP_VERSION", "1.0.0")
        event_dict["hostname"] = socket.gethostname()
        event_dict["process_id"] = os.getpid()
        event_dict["thread_name"] = threading.current_thread().name
        # Container / orchestration context (populated via env vars in K8s/ECS)
        pod_name = os.getenv("POD_NAME")
        if pod_name:
            event_dict["pod_name"] = pod_name
        container_id = os.getenv("CONTAINER_ID")
        if container_id:
            event_dict["container_id"] = container_id
        deployment_id = os.getenv("DEPLOYMENT_ID")
        if deployment_id:
            event_dict["deployment_id"] = deployment_id

    return event_dict


def configure_logging(env: str) -> None:
    """Configure structured logging with environment-aware formatting.

    - **development**: Human-readable coloured console output (no JSON).
    - **production / staging**: JSON output to both console and rotating file,
      suitable for log aggregation tools (ELK, Datadog, etc.).
    """
    is_dev = env == "development"

    # --- Shared processors (run regardless of environment) ----------------
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", key="timestamp"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        add_app_context,
    ]

    # In production, include callsite info for debugging prod issues
    if not is_dev:
        shared_processors.insert(
            4,
            structlog.processors.CallsiteParameterAdder(
                {
                    structlog.processors.CallsiteParameter.FILENAME: "file",
                    structlog.processors.CallsiteParameter.LINENO: "line",
                    structlog.processors.CallsiteParameter.FUNC_NAME: "method",
                }
            ),
        )

    structlog.configure(
        processors=shared_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # --- Console handler --------------------------------------------------
    console_handler = logging.StreamHandler(sys.stdout)

    if is_dev:
        # Readable, coloured output for local development
        console_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(),
        )
    else:
        # Structured JSON for production log pipelines
        console_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
        )

    console_handler.setFormatter(console_formatter)

    # --- Root logger setup ------------------------------------------------
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if is_dev else logging.INFO)
    root_logger.handlers = []
    root_logger.addHandler(console_handler)

    # --- File handlers (production / staging only) -------------------------
    if not is_dev:
        root_dir = Path(__file__).resolve().parent.parent.parent
        log_dir = root_dir / "logs"
        log_dir.mkdir(exist_ok=True)

        json_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
        )

        # All logs → app.log
        app_handler = TimedRotatingFileHandler(
            log_dir / "app.log",
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        app_handler.setFormatter(json_formatter)
        root_logger.addHandler(app_handler)

        # Errors only → error.log
        error_handler = TimedRotatingFileHandler(
            log_dir / "error.log",
            when="midnight",
            interval=1,
            backupCount=60,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.WARNING)
        error_handler.setFormatter(json_formatter)
        root_logger.addHandler(error_handler)

    # --- Quiet noisy library loggers --------------------------------------
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


logger = structlog.get_logger(__name__)