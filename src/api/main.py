"""FastAPI application factory."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    Base.metadata.create_all(bind=engine)
    try:
        import alembic.config
        import alembic.command
        alembic_cfg = alembic.config.Config("alembic.ini")
        alembic.command.upgrade(alembic_cfg, "head")
    except Exception:
        pass  # Alembic not configured or DB already up-to-date
    yield
    # Shutdown


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "development" else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging
app.add_middleware(RequestLoggingMiddleware)

# API routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
app.include_router(runs.router, prefix="/api/v1/runs", tags=["runs"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(video.router, prefix="", tags=["video"])
app.include_router(agents.router, prefix="", tags=["agents"])
app.include_router(evaluation.router, prefix="", tags=["evaluation"])
app.include_router(apikeys.router, prefix="/api/v1/auth/api-keys", tags=["auth"])
app.include_router(metrics_router.router, prefix="", tags=["metrics"])


# Static web UI (will serve index.html from src/web/static/)
# Create directory if it doesn't exist to avoid startup crash
os.makedirs("src/web/static", exist_ok=True)
app.mount("/", StaticFiles(directory="src/web/static", html=True), name="static")