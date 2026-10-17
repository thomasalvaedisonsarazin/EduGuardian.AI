"""Intervention plan endpoints (Module 5): review queue, edits, approvals."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import TenantContext, get_db, require_roles
from app.models import InterventionStatus
from app.schemas.interventions import (
    InterventionList,
    InterventionOut,
    InterventionUpdate,
    RejectRequest,
    StatusUpdate,
)
from app.services import intervention_service as svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interventions", tags=["interventions"])

_member = require_roles()


@router.get("", response_model=InterventionList)
def list_interventions(
    status: InterventionStatus | None = None,
    class_section_id: int | None = Query(default=None, alias="class_section_id"),
    class_id: int | None = Query(default=None, description="Alias of class_section_id"),
    exam_id: int | None = None,
    run_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: TenantContext = Depends(_member),
    db: Session = Depends(get_db),
) -> InterventionList:
    """Plans of the active school (teachers: only their classes), newest first."""
    return svc.list_plans(
        db,
        ctx,
        status=status,
        class_section_id=class_section_id if class_section_id is not None else class_id,
        exam_id=exam_id,
        run_id=run_id,
        limit=limit,
        offset=offset,
    )


@router.get("/{plan_id}", response_model=InterventionOut)
def get_intervention(
    plan_id: int, ctx: TenantContext = Depends(_member), db: Session = Depends(get_db)
) -> InterventionOut:
    return svc.get_plan(db, ctx, plan_id)


@router.put("/{plan_id}", response_model=InterventionOut)
def update_intervention(
    plan_id: int,
    body: InterventionUpdate,
    ctx: TenantContext = Depends(_member),
    db: Session = Depends(get_db),
) -> InterventionOut:
    """Edit a draft plan (plan text, activities, reassessment date)."""
    return svc.update_plan(db, ctx, plan_id, body)


@router.post("/{plan_id}/approve", response_model=InterventionOut)
def approve_intervention(
    plan_id: int, ctx: TenantContext = Depends(_member), db: Session = Depends(get_db)
) -> InterventionOut:
    return svc.approve_plan(db, ctx, plan_id)


@router.post("/{plan_id}/reject", response_model=InterventionOut)
def reject_intervention(
    plan_id: int,
    body: RejectRequest | None = None,
    ctx: TenantContext = Depends(_member),
    db: Session = Depends(get_db),
) -> InterventionOut:
    return svc.reject_plan(db, ctx, plan_id, body or RejectRequest())


@router.patch("/{plan_id}/status", response_model=InterventionOut)
def change_intervention_status(
    plan_id: int,
    body: StatusUpdate,
    ctx: TenantContext = Depends(_member),
    db: Session = Depends(get_db),
) -> InterventionOut:
    """approved -> in_progress -> completed."""
    return svc.change_status(db, ctx, plan_id, body)
