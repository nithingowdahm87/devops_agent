"""Audit log model for tracking data changes."""
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.sql import func
from src.db.database import Base


class AuditLog(Base):
    """Records user actions for audit and compliance purposes."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(50), nullable=False)  # CREATE, UPDATE, DELETE
    table_name = Column(String(100), nullable=False)
    record_id = Column(Integer, nullable=False)
    old_values = Column(Text, nullable=True)  # JSON
    new_values = Column(Text, nullable=True)  # JSON
    created_at = Column(DateTime(timezone=True), server_default=func.now())