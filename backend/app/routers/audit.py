"""Audit log endpoints (Module 5): every agent step, approval and data change."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import TenantContext, get_db, require_roles
from app.models import MembershipRole
from app.schemas.audit import AuditLogList
from app.services import audit_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit-logs", tags=["audit"])

_auditor = require_roles(
    MembershipRole.school_admin, MembershipRole.principal, MembershipRole.coordinator
)


@router.get("", response_model=AuditLogList)
def list_audit_logs(
    entity_type: str | None = None,
    actor: str | None = Query(
        default=None, description='"user", "agents" (any agent) or an agent name'
    ),
    entity_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: TenantContext = Depends(_auditor),
    db: Session = Depends(get_db),
) -> AuditLogList:
    """Newest-first audit entries of the active school with the acting user's email."""
    return audit_service.list_logs(
        db,
        ctx.school_id,
        entity_type=entity_type,
        actor=actor,
        entity_id=entity_id,
        limit=limit,
        offset=offset,
    )
