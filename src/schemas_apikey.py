from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class ApiKeyCreate(BaseModel):
    name: str
    scopes: Optional[list] = None

class ApiKeyRead(BaseModel):
    id: int
    name: str
    scopes: Optional[list]
    is_active: bool
    created_at: Optional[datetime]
    last_used_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)

class ApiKeyCreatedResponse(BaseModel):
    id: int
    name: str
    key: str  # plain key, shown once
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)