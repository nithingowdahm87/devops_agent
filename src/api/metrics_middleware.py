import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from src.observability.metrics import REQUEST_TIME, REQUEST_COUNT

class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start
        method = request.method
        endpoint = request.url.path
        status = str(response.status_code)
        REQUEST_TIME.labels(method=method, endpoint=endpoint, status=status).observe(duration)
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
        return response