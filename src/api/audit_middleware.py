"""Audit logging middleware for FastAPI."""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from src.db.database import SessionLocal
from src.db import crud_audit
import json


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Log mutating requests (POST, PUT, PATCH, DELETE) to the audit log table.

    Only logs successful responses (status_code < 400).
    Extracts user_id from request.state if populated by auth middleware.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if request.method in ("POST", "PUT", "PATCH", "DELETE") and response.status_code < 400:
            db = SessionLocal()
            try:
                user_id = getattr(request.state, "user_id", None)
                if user_id:
                    crud_audit.log_audit(
                        db,
                        user_id=user_id,
                        action=request.method,
                        table_name=request.url.path.split("/")[-2] or "unknown",
                        record_id=0,  # simplified; override per-endpoint for accuracy
                        new_values={"path": str(request.url)},
                    )
            except Exception:
                # Never let audit logging break the request
                pass
            finally:
                db.close()

        return response