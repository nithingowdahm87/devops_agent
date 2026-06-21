"""Video generation endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from src.db.database import get_db
from src.db import crud_video, models_video
from src.db.models import User
from src.schemas_video import VideoTaskCreate, VideoTaskRead
from src.api.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/video", tags=["video"])


@router.post("/jobs", response_model=VideoTaskRead, status_code=status.HTTP_201_CREATED)
def create_video_job(
    task: VideoTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new video generation job."""
    db_task = crud_video.create_video_task(
        db,
        user_id=current_user.id,
        prompt=task.prompt,
        project_id=task.project_id,
    )
    return db_task


@router.get("/jobs", response_model=List[VideoTaskRead])
def list_video_jobs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all video tasks for the current user."""
    return crud_video.get_video_tasks(db, current_user.id, skip=skip, limit=limit)


@router.get("/jobs/{task_id}", response_model=VideoTaskRead)
def get_video_job(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific video task by ID."""
    task = crud_video.get_video_task(db, task_id, current_user.id)
    if not task:
        raise HTTPException(status_code=404, detail="Video task not found")
    return task