"""CRUD operations for video tasks."""
from sqlalchemy.orm import Session
from src.db.models_video import VideoTask


def create_video_task(db: Session, user_id: int, prompt: str, project_id: int | None = None):
    """Create a new video task."""
    task = VideoTask(user_id=user_id, project_id=project_id, prompt=prompt)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_video_tasks(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    """Get all video tasks for a user."""
    return db.query(VideoTask).filter(
        VideoTask.user_id == user_id
    ).order_by(VideoTask.created_at.desc()).offset(skip).limit(limit).all()


def get_video_task(db: Session, task_id: int, user_id: int):
    """Get a single video task by ID."""
    return db.query(VideoTask).filter(
        VideoTask.id == task_id,
        VideoTask.user_id == user_id
    ).first()


def update_video_task(db: Session, task_id: int, user_id: int, **kwargs):
    """Update a video task."""
    task = get_video_task(db, task_id, user_id)
    if not task:
        return None
    for key, value in kwargs.items():
        if value is not None and hasattr(task, key):
            setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task


def delete_video_task(db: Session, task_id: int, user_id: int):
    """Delete a video task."""
    task = get_video_task(db, task_id, user_id)
    if task:
        db.delete(task)
        db.commit()
        return True
    return False