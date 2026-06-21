"""Soft delete mixin for SQLAlchemy models."""
from sqlalchemy import Column, DateTime, Integer, ForeignKey
from sqlalchemy.sql import func


class SoftDeleteMixin:
    """Mixin that adds soft-delete fields to a model."""
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(Integer, ForeignKey("users.id"), nullable=True)


def filter_not_deleted(query):
    """Append soft-delete filter to a query.

    Filters out records where deleted_at is not NULL.
    Note: Requires the model to have a deleted_at column.
    """
    # Access the first entity in the query to reference its type
    entity = query.column_descriptions[0]["type"]
    return query.filter(entity.deleted_at == None)