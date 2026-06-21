"""Pydantic schemas for evaluation."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class EvaluationCreate(BaseModel):
    predictions: list[Any]
    ground_truth: list[Any]
    project_id: Optional[int] = None


class EvaluationRead(BaseModel):
    id: int
    metric: str
    score: float
    predictions: Any
    ground_truth: Any
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvaluationRequest(BaseModel):
    predictions: list[Any]
    ground_truth: list[Any]
    project_id: Optional[int] = None