"""Video task schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class VideoTaskCreate(BaseModel):
    """Schema for creating a video task."""
    prompt: str
    project_id: Optional[int] = None


class VideoTaskRead(BaseModel):
    """Schema for reading a video task."""
    id: int
    project_id: Optional[int]
    prompt: str
    status: str
    result_url: Optional[str]
    created_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class VideoTaskUpdate(BaseModel):
    """Schema for updating a video task."""
    status: Optional[str] = None
    result_url: Optional[str] = None