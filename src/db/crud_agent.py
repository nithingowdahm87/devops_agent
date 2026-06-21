"""CRUD operations for Agent model."""
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from src.db import models_agent


def create_agent(db: Session, user_id: int, name: str, capabilities: str = None):
    agent = models_agent.Agent(
        user_id=user_id,
        name=name,
        capabilities=capabilities,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def get_agents(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models_agent.Agent).filter(
        models_agent.Agent.user_id == user_id
    ).offset(skip).limit(limit).all()


def get_agent(db: Session, agent_id: int, user_id: int):
    return db.query(models_agent.Agent).filter(
        models_agent.Agent.id == agent_id,
        models_agent.Agent.user_id == user_id
    ).first()


def update_agent(db: Session, agent_id: int, user_id: int, **kwargs):
    agent = get_agent(db, agent_id, user_id)
    if not agent:
        return None
    for key, value in kwargs.items():
        if value is not None and hasattr(agent, key):
            setattr(agent, key, value)
    db.commit()
    db.refresh(agent)
    return agent


def delete_agent(db: Session, agent_id: int, user_id: int):
    agent = get_agent(db, agent_id, user_id)
    if not agent:
        return False
    db.delete(agent)
    db.commit()
    return True


def update_heartbeat(db: Session, agent_id: int, user_id: int):
    agent = get_agent(db, agent_id, user_id)
    if not agent:
        return None
    agent.last_heartbeat = datetime.now(timezone.utc)
    db.commit()
    db.refresh(agent)
    return agent