from __future__ import annotations

import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Clear contextvars to avoid leakage between requests
        clear_contextvars()

        # Extract x-request-id from headers or generate a new one
        # Format: req-<8-char-hex>
        incoming = request.headers.get("x-request-id", "")
        if incoming and incoming.startswith("req-") and len(incoming) == 12:
            correlation_id = incoming
        else:
            correlation_id = "req-" + uuid.uuid4().hex[:8]

        # Bind the correlation_id to structlog contextvars so every log in this request has it
        bind_contextvars(correlation_id=correlation_id)

        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Add correlation_id and processing time to response headers
        response.headers["x-request-id"] = correlation_id
        response.headers["x-response-time-ms"] = f"{elapsed_ms:.1f}"

        return response
