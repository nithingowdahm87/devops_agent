"""Pydantic schemas for Agent."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AgentCreate(BaseModel):
    name: str
    capabilities: Optional[str] = None


class AgentRead(BaseModel):
    id: int
    name: str
    status: str
    last_heartbeat: Optional[datetime]
    capabilities: Optional[str]
    created_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    capabilities: Optional[str] = None


class HeartbeatUpdate(BaseModel):
    status: str