"""Audit-log helper shared by every module. Adds the row to the session; the caller commits."""

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog


def log_action(
    db: Session,
    *,
    school_id: int,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: int | None = None,
    user_id: int | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditLog:
    """Record an action. ``actor`` is ``"user"`` or an agent name such as ``"DataQualityAgent"``."""
    entry = AuditLog(
        school_id=school_id,
        user_id=user_id,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        detail=detail or {},
    )
    db.add(entry)
    return entry
