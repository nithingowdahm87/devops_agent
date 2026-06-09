"""Project management endpoints."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from typing import List

from src.db.database import get_db
from src.db import crud, models
from src.api.dependencies import get_current_user

router = APIRouter()

class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    repo_url: str | None = None

class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None
    repo_url: str | None
    created_at: datetime | None
    
    model_config = ConfigDict(from_attributes=True)

@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_project = crud.create_project(
        db, name=project.name, owner_id=current_user.id,
        description=project.description, repo_url=project.repo_url
    )
    return db_project

@router.get("/", response_model=List[ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_projects_by_owner(db, current_user.id)

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = crud.get_project(db, project_id, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project