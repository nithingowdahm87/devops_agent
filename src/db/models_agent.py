"""Agent database model."""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from src.db.database import Base


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    status = Column(String(50), default="idle")  # idle|busy|offline
    last_heartbeat = Column(DateTime(timezone=True), nullable=True)
    capabilities = Column(Text, nullable=True)  # JSON string
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())