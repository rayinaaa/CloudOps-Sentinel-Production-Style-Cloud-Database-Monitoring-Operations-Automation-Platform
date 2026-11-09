"""CloudOps Sentinel Structured Logging Configuration.

Configures JSON structured logging in production environments for seamless
ingestion into AWS CloudWatch, Datadog, and Grafana Loki, while providing
readable colored logs in local development.
"""

import logging
import re
import sys

import structlog

from app.core.config import settings

SENSITIVE_KEY_PATTERNS = {
    "password",
    "secret",
    "token",
    "authorization",
    "api_key",
    "private_key",
}
URI_PASSWORD_PATTERN = re.compile(r"://([^:@]+):([^@]+)@")


def redact_sensitive_data(logger, method_name, event_dict):
    """Masks credentials, passwords, and tokens from structured log payloads."""
    for key in list(event_dict.keys()):
        key_lower = key.lower()
        if any(sens in key_lower for sens in SENSITIVE_KEY_PATTERNS):
            event_dict[key] = "[REDACTED]"
        elif isinstance(event_dict[key], str):
            event_dict[key] = URI_PASSWORD_PATTERN.sub(r"://\1:***@", event_dict[key])
    return event_dict


def setup_logging() -> None:
    """Initialize structured logging pipelines based on runtime environment."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        redact_sensitive_data,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.ENVIRONMENT.lower() == "production":
        # Production JSON renderer for CloudWatch / Loki ingestion
        final_processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development readable console renderer
        final_processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=final_processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


logger = structlog.get_logger("cloudops.sentinel")
