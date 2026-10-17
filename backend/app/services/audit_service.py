"""Read side of the audit log (writes go through ``app.services.audit.log_action``)."""

from __future__ import annotations

import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, User
from app.schemas.audit import AuditLogList, AuditLogOut

logger = logging.getLogger(__name__)

MAX_LIMIT = 200
#: Special ``actor`` filter values.
ACTOR_USERS = "user"
ACTOR_AGENTS = "agents"


def list_logs(
    db: Session,
    school_id: int,
    *,
    entity_type: str | None = None,
    actor: str | None = None,
    entity_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> AuditLogList:
    """Newest-first audit entries. ``actor="agents"`` matches every non-user actor."""
    filters = [AuditLog.school_id == school_id]
    if entity_type:
        filters.append(AuditLog.entity_type == entity_type)
    if actor == ACTOR_AGENTS:
        filters.append(AuditLog.actor != ACTOR_USERS)
    elif actor:
        filters.append(AuditLog.actor == actor)
    if entity_id is not None:
        filters.append(AuditLog.entity_id == entity_id)

    total = db.scalar(select(func.count(AuditLog.id)).where(*filters)) or 0
    rows = db.execute(
        select(AuditLog, User.email)
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(*filters)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(max(1, min(limit, MAX_LIMIT)))
        .offset(max(0, offset))
    ).all()
    actors = sorted(
        db.scalars(select(AuditLog.actor).where(AuditLog.school_id == school_id).distinct())
    )
    entity_types = sorted(
        db.scalars(select(AuditLog.entity_type).where(AuditLog.school_id == school_id).distinct())
    )
    return AuditLogList(
        items=[
            AuditLogOut(
                id=log.id,
                user_id=log.user_id,
                user_email=email,
                actor=log.actor,
                action=log.action,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                detail=log.detail,
                created_at=log.created_at,
            )
            for log, email in rows
        ],
        total=total,
        actors=actors,
        entity_types=entity_types,
    )
