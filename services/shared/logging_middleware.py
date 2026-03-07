"""
OpenClaw Army — Structured Logging Middleware
=============================================

Provides:
1. Correlation ID tracking (X-Correlation-ID header)
2. Request/response logging with timing
3. JSON-structured log output for production
"""

import logging
import os
import time
import uuid
from contextvars import ContextVar
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# Correlation ID context var — accessible from any async code in the request
correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


class CorrelationFilter(logging.Filter):
    """Inject correlation ID into log records."""
    def filter(self, record):
        record.correlation_id = correlation_id.get("---")
        return True


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that adds correlation IDs and request logging."""

    def __init__(self, app, service_name: str = "unknown"):
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Get or generate correlation ID
        corr_id = request.headers.get("x-correlation-id", str(uuid.uuid4())[:12])
        correlation_id.set(corr_id)

        start = time.time()
        logger = logging.getLogger(self.service_name)

        logger.info(
            f"REQ {request.method} {request.url.path} corr={corr_id}"
        )

        try:
            response = await call_next(request)
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            logger.error(
                f"ERR {request.method} {request.url.path} "
                f"exception={type(e).__name__} elapsed={elapsed:.1f}ms corr={corr_id}"
            )
            raise

        elapsed = (time.time() - start) * 1000
        logger.info(
            f"RES {request.method} {request.url.path} "
            f"status={response.status_code} elapsed={elapsed:.1f}ms corr={corr_id}"
        )

        response.headers["x-correlation-id"] = corr_id
        return response


def setup_logging(service_name: str, level: str = "INFO"):
    """Configure structured logging for a service."""
    log_format = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s [%(name)s] %(levelname)s [%(correlation_id)s] %(message)s"
    )
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(log_format))
    handler.addFilter(CorrelationFilter())

    logger = logging.getLogger(service_name)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.propagate = False
    return logger
