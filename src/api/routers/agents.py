"""Agent management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from typing import List

from src.db.database import get_db
from src.db import crud_agent
from src.db.models_agent import Agent
from src.db import models
from src.schemas_agent import AgentCreate, AgentRead, HeartbeatUpdate
from src.api.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.post("/", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
def create_agent(
    agent_data: AgentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Register a new agent."""
    agent = crud_agent.create_agent(
        db,
        user_id=current_user.id,
        name=agent_data.name,
        capabilities=agent_data.capabilities,
    )
    return agent


@router.get("/", response_model=List[AgentRead])
def list_agents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List all agents for the current user."""
    return crud_agent.get_agents(db, current_user.id)


@router.get("/{agent_id}", response_model=AgentRead)
def get_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Get a specific agent by ID."""
    agent = crud_agent.get_agent(db, agent_id, current_user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/{agent_id}/heartbeat", response_model=AgentRead)
def update_heartbeat(
    agent_id: int,
    heartbeat: HeartbeatUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Update agent heartbeat and status."""
    agent = crud_agent.update_heartbeat(db, agent_id, current_user.id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent = crud_agent.update_agent(db, agent_id, current_user.id, status=heartbeat.status)
    return agent