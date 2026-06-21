from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add production security headers to all responses."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject requests with bodies larger than max_body_size bytes."""
    def __init__(self, app, max_body_size: int = 10 * 1024 * 1024):
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.max_body_size:
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Request body too large. Max size: {self.max_body_size} bytes"}
                )
        return await call_next(request)