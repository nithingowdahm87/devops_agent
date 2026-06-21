"""CRUD operations for audit logs."""
import json
from sqlalchemy.orm import Session
from src.db.models_audit import AuditLog


def log_audit(
    db: Session,
    user_id: int | None,
    action: str,
    table_name: str,
    record_id: int,
    old_values: dict | None = None,
    new_values: dict | None = None,
) -> AuditLog:
    """Create an audit log entry.

    Args:
        db: Database session.
        user_id: ID of the user performing the action.
        action: One of CREATE, UPDATE, DELETE.
        table_name: Name of the affected table.
        record_id: Primary key of the affected record.
        old_values: State before the change (for UPDATE/DELETE).
        new_values: State after the change (for CREATE/UPDATE).

    Returns:
        The created AuditLog entry.
    """
    entry = AuditLog(
        user_id=user_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_values=json.dumps(old_values) if old_values else None,
        new_values=json.dumps(new_values) if new_values else None,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry