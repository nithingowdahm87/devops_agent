"""CRUD operations for evaluation results."""
import json
from sqlalchemy.orm import Session
from src.db.models_evaluation import EvaluationResult


def create_evaluation(
    db: Session,
    user_id: int,
    predictions: list,
    ground_truth: list,
    score: float,
    metric: str = "cohens_kappa",
    project_id: int | None = None,
):
    evaluation = EvaluationResult(
        user_id=user_id,
        project_id=project_id,
        metric=metric,
        score=score,
        predictions=json.dumps(predictions),
        ground_truth=json.dumps(ground_truth),
    )
    db.add(evaluation)
    db.commit()
    db.refresh(evaluation)
    return evaluation


def get_evaluations(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return (
        db.query(EvaluationResult)
        .filter(EvaluationResult.user_id == user_id)
        .order_by(EvaluationResult.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_evaluation(db: Session, eval_id: int, user_id: int):
    return (
        db.query(EvaluationResult)
        .filter(
            EvaluationResult.id == eval_id,
            EvaluationResult.user_id == user_id,
        )
        .first()
    )


def delete_evaluation(db: Session, eval_id: int, user_id: int):
    evaluation = get_evaluation(db, eval_id, user_id)
    if evaluation:
        db.delete(evaluation)
        db.commit()
    return evaluation