"""Pipeline run endpoints."""
import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.db.database import get_db
from src.db import crud, models
from src.api.dependencies import get_current_user
from src.services.pipeline_service import PipelineService

router = APIRouter()
pipeline_service = PipelineService()

class RunCreate(BaseModel):
    project_id: int
    config: dict | None = None
    no_heal: bool = False

@router.post("/", status_code=status.HTTP_202_ACCEPTED)
def start_run(
    run: RunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = crud.get_project(db, run.project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    db_run = crud.create_run(db, project_id=run.project_id, config=json.dumps(run.config or {}))
    
    background_tasks.add_task(
        _execute_pipeline,
        run_id=db_run.id,
        project_path=project.repo_url or "",
        config=run.config,
        no_heal=run.no_heal,
    )
    
    return {"run_id": db_run.id, "status": "started"}


def _execute_pipeline(run_id: int, project_path: str, config: dict | None, no_heal: bool):
    """Background task for pipeline execution."""
    from src.db.database import SessionLocal
    db = SessionLocal()
    try:
        crud.update_run_status(db, run_id, status="running", stage="analyzing")
        
        # Run the pipeline (sync wrapper for async)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(
            pipeline_service.run(project_path, config=config, no_heal=no_heal)
        )
        loop.close()
        
        status = "failed" if results.get("errors") else "completed"
        crud.update_run_status(
            db, run_id,
            status=status,
            stage="done",
            results=json.dumps(results),
            logs="\n".join(results.get("logs", [])),
        )
    except Exception as e:
        crud.update_run_status(db, run_id, status="failed", stage="error", logs=str(e))
    finally:
        db.close()

@router.get("/{run_id}")
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    run = crud.get_run(db, run_id, current_user.id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": run.id,
        "project_id": run.project_id,
        "status": run.status,
        "stage": run.stage,
        "results": json.loads(run.results) if run.results else None,
        "logs": run.logs,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }

@router.get("/")
def list_runs(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    runs = crud.get_runs_by_project(db, project_id, current_user.id)
    return [{"id": r.id, "status": r.status, "stage": r.stage, "created_at": r.created_at.isoformat() if r.created_at else None} for r in runs]