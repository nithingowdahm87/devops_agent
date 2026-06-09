"""Admin/monitoring endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.db.database import get_db, engine
from src.db import models
from src.config.settings import settings
import time

router = APIRouter()
start_time = time.time()

@router.get("/health")
def health_check():
    return { "status": "ok", "version": settings.APP_VERSION, "environment": settings.ENVIRONMENT, "uptime_seconds": round(time.time() - start_time, 1) }

@router.get("/db-check")
def db_check(db: Session = Depends(get_db)):
    try:
        db.execute("SELECT 1")
        return {"status": "connected"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    users = db.query(models.User).count()
    projects = db.query(models.Project).count()
    runs = db.query(models.Run).count()
    return {"users": users, "projects": projects, "runs": runs, "version": settings.APP_VERSION}