"""FastAPI middleware."""
import time
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from loguru import logger

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start
        logger.info(
            f"{request.method} {request.url.path} — {response.status_code} ({duration:.3f}s)"
        )
        return response