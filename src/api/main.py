"""FastAPI application factory."""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.observability.logging import setup_logging
from src.db.database import engine, Base
from src.api.routers import auth, projects, runs, admin, video, agents, evaluation
from src.api.middleware import RequestLoggingMiddleware
import os

from src.api.security_middleware import SecurityHeadersMiddleware, MaxBodySizeMiddleware
from src.api.metrics_middleware import PrometheusMiddleware
from src.api.audit_middleware import AuditLogMiddleware
from src.api.routers import apikeys, metrics as metrics_router

from src.config.settings import settings
from src.api.rate_limit import check_limit


def rate_limit_dependency(request: Request):
    """Dependency that enforces the default rate limit on every request."""
    client_ip = request.client.host if request.client else "unknown"
    key = f"{client_ip}:{request.url.path}"
    if not check_limit(key, settings.RATE_LIMIT_DEFAULT):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def rate_limit_write_dependency(request: Request):
    """Dependency that enforces the stricter write rate limit."""
    client_ip = request.client.host if request.client else "unknown"
    key = f"write:{client_ip}:{request.url.path}"
    if not check_limit(key, settings.RATE_LIMIT_WRITE):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    if settings.ENVIRONMENT == "development":
        Base.metadata.create_all(bind=engine)
        try:
            import alembic.config
            import alembic.command
            alembic_cfg = alembic.config.Config("alembic.ini")
            alembic.command.upgrade(alembic_cfg, "head")
        except Exception:
            pass
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Security headers
app.add_middleware(SecurityHeadersMiddleware)

# Max body size limit
app.add_middleware(MaxBodySizeMiddleware, max_body_size=settings.MAX_REQUEST_BODY_SIZE_MB * 1024 * 1024)

# Prometheus metrics
app.add_middleware(PrometheusMiddleware)

# Audit logging
app.add_middleware(AuditLogMiddleware)

# CORS
origins = [o.strip() for o in settings.CORS_ALLOWED_ORIGINS.split(",") if o.strip()] if settings.CORS_ALLOWED_ORIGINS else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging
app.add_middleware(RequestLoggingMiddleware)

# API routers — rate-limit all endpoints by default; write endpoints use stricter limit
# Read endpoints: projects list, runs list, agents list
_read_routers = [
    (projects.router, "/api/v1/projects", ["projects"]),
    (runs.router, "/api/v1/runs", ["runs"]),
    (agents.router, "", ["agents"]),
]
# Write endpoints (stricter rate limit)
_write_routers = [
    (auth.router, "/api/v1/auth", ["auth"]),
]

for _router, _prefix, _tags in _read_routers:
    app.include_router(
        _router,
        prefix=_prefix,
        tags=_tags,
        dependencies=[Depends(rate_limit_dependency)],
    )

for _router, _prefix, _tags in _write_routers:
    app.include_router(
        _router,
        prefix=_prefix,
        tags=_tags,
        dependencies=[Depends(rate_limit_write_dependency)],
    )

app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(video.router, prefix="", tags=["video"])
app.include_router(evaluation.router, prefix="", tags=["evaluation"])
app.include_router(apikeys.router, prefix="/api/v1/auth/api-keys", tags=["auth"])
app.include_router(metrics_router.router, prefix="", tags=["metrics"])


# Static web UI (will serve index.html from src/web/static/)
# Create directory if it doesn't exist to avoid startup crash
os.makedirs("src/web/static", exist_ok=True)
app.mount("/ui/", StaticFiles(directory="src/web/static", html=True), name="static")