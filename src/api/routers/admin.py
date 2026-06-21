"""Admin/monitoring endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.db.database import get_db, engine
from src.db import models
from src.db.models_video import VideoTask
from src.db.models_agent import Agent
from src.db.models_evaluation import EvaluationResult
from src.config.settings import settings
from src.observability.health import check_db, check_redis, check_external_apis
import time

router = APIRouter()
start_time = time.time()

@router.get("/health")
def health_check():
    return { "status": "ok", "version": settings.APP_VERSION, "environment": settings.ENVIRONMENT, "uptime_seconds": round(time.time() - start_time, 1) }

@router.get("/ready")
async def readiness_check(db: Session = Depends(get_db)):
    """Readiness check: DB + Redis + external APIs"""
    db_health = await check_db(db)
    redis_health = await check_redis()
    external = await check_external_apis()
    
    is_ready = db_health["status"] == "healthy" and redis_health["status"] in ("healthy", "skipped")
    return {
        "ready": is_ready,
        "checks": {
            "database": db_health,
            "redis": redis_health,
            "external_apis": external
        }
    }

@router.get("/health/deep")
async def deep_health_check(db: Session = Depends(get_db)):
    """Full deep health check with latencies"""
    db_health = await check_db(db)
    redis_health = await check_redis()
    external = await check_external_apis()
    
    return {
        "status": "ok" if db_health["status"] == "healthy" else "degraded",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "uptime_seconds": round(time.time() - start_time, 1),
        "checks": {
            "database": db_health,
            "redis": redis_health,
            "external_apis": external
        }
    }

@router.get("/db-check")
def db_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "connected"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    users = db.query(models.User).count()
    projects = db.query(models.Project).count()
    runs = db.query(models.Run).count()
    video_tasks = db.query(VideoTask).count()
    agents = db.query(Agent).count()
    evaluations = db.query(EvaluationResult).count()
    return {
        "users": users,
        "projects": projects,
        "runs": runs,
        "video_tasks": video_tasks,
        "agents": agents,
        "evaluations": evaluations,
        "version": settings.APP_VERSION,
    }