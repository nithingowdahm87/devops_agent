"""Evaluation endpoints."""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ConfigDict
from typing import Any, Optional

from src.db.database import get_db
from src.db import models as db_models
from src.db import crud_evaluation
from src.schemas_evaluation import EvaluationRequest, EvaluationRead
from src.evaluation.kappa import cohens_kappa
from src.api.dependencies import get_current_user

router = APIRouter(prefix="/api/v1/evaluation", tags=["evaluation"])


def _eval_to_dict(e) -> dict[str, Any]:
    return {
        "id": e.id,
        "metric": e.metric,
        "score": e.score,
        "predictions": json.loads(e.predictions) if e.predictions else None,
        "ground_truth": json.loads(e.ground_truth) if e.ground_truth else None,
        "project_id": e.project_id,
        "user_id": e.user_id,
        "created_at": e.created_at,
        "updated_at": e.updated_at,
    }


class ScoreResponse(BaseModel):
    id: int
    metric: str
    score: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.post("/", response_model=ScoreResponse, status_code=status.HTTP_201_CREATED)
def evaluate(
    request: EvaluationRequest,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Compute Cohen's kappa score and store the evaluation result."""
    score = cohens_kappa(request.predictions, request.ground_truth)
    evaluation = crud_evaluation.create_evaluation(
        db,
        user_id=current_user.id,
        predictions=request.predictions,
        ground_truth=request.ground_truth,
        score=score,
        metric="cohens_kappa",
        project_id=request.project_id,
    )
    return evaluation


@router.get("/", response_model=list[EvaluationRead])
def list_evaluations(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """List all evaluation results for the current user."""
    evaluations = crud_evaluation.get_evaluations(db, current_user.id, skip, limit)
    return [_eval_to_dict(e) for e in evaluations]


@router.get("/{eval_id}", response_model=EvaluationRead)
def get_evaluation(
    eval_id: int,
    db: Session = Depends(get_db),
    current_user: db_models.User = Depends(get_current_user),
):
    """Get a specific evaluation result by ID."""
    evaluation = crud_evaluation.get_evaluation(db, eval_id, current_user.id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return _eval_to_dict(evaluation)