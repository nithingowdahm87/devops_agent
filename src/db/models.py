"""Database models."""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    repo_url = Column(String(500), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="projects")
    runs = relationship("Run", back_populates="project", cascade="all, delete-orphan")


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    stage = Column(String(50), default="queued")
    config = Column(Text, nullable=True)  # JSON string
    results = Column(Text, nullable=True)  # JSON string
    logs = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    project = relationship("Project", back_populates="runs")

# Imported models — relationships managed in their own modules
from src.db.models_video import VideoTask  # noqa: F401,E402
from src.db.models_agent import Agent  # noqa: F401,E402
from src.db.models_evaluation import EvaluationResult  # noqa: F401,E402
from src.db.models_apikey import ApiKey  # noqa: F401,E402
from src.db.models_audit import AuditLog  # noqa: F401,E402