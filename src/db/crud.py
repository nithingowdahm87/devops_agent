"""CRUD operations for DB models."""
from sqlalchemy.orm import Session
from src.db import models


def create_user(db: Session, email: str, hashed_password: str):
    user = models.User(email=email, hashed_password=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


def create_project(db: Session, name: str, owner_id: int, description: str = None, repo_url: str = None):
    project = models.Project(name=name, owner_id=owner_id, description=description, repo_url=repo_url)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_projects_by_owner(db: Session, owner_id: int):
    return db.query(models.Project).filter(models.Project.owner_id == owner_id).all()


def get_project(db: Session, project_id: int, owner_id: int):
    return db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.owner_id == owner_id
    ).first()


def create_run(db: Session, project_id: int, config: str = None):
    run = models.Run(project_id=project_id, config=config)
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get_run(db: Session, run_id: int, owner_id: int):
    from sqlalchemy.orm import joinedload
    return db.query(models.Run).options(joinedload(models.Run.project)).filter(
        models.Run.id == run_id,
        models.Run.project.has(owner_id=owner_id)
    ).first()


def update_run_status(db: Session, run_id: int, status: str, stage: str = None, results: str = None, logs: str = None):
    run = db.query(models.Run).filter(models.Run.id == run_id).first()
    if run:
        if status:
            run.status = status
        if stage:
            run.stage = stage
        if results:
            run.results = results
        if logs:
            run.logs = logs
        db.commit()
        db.refresh(run)
    return run


def get_runs_by_project(db: Session, project_id: int, owner_id: int):
    return db.query(models.Run).join(models.Project).filter(
        models.Run.project_id == project_id,
        models.Project.owner_id == owner_id
    ).order_by(models.Run.created_at.desc()).all()