from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey, Text
from sqlalchemy.sql import func
from src.db.database import Base


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    metric = Column(String(100), nullable=False)
    score = Column(Float, nullable=False)
    predictions = Column(Text, nullable=True)  # JSON string
    ground_truth = Column(Text, nullable=True)  # JSON string
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())