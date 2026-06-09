"""FastAPI application factory."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.observability.logging import setup_logging
from src.db.database import engine, Base
from src.api.routers import auth, projects, runs, admin
from src.api.middleware import RequestLoggingMiddleware
from src.config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    Base.metadata.create_all(bind=engine)
    yield
    # Shutdown


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

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

# Static web UI (will serve index.html from src/web/static/)
# Create directory if it doesn't exist to avoid startup crash
import os
os.makedirs("src/web/static", exist_ok=True)
app.mount("/", StaticFiles(directory="src/web/static", html=True), name="static")