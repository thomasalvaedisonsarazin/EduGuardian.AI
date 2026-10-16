"""School endpoints for the active school (X-School-Id): info and member management."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies import TenantContext, get_db, get_tenant_context, require_roles
from app.models import MembershipRole
from app.schemas.schools import (
    MemberCreate,
    MemberCreated,
    MemberOut,
    MemberRoleUpdate,
    SchoolOut,
)
from app.services import school_service

router = APIRouter(prefix="/schools", tags=["schools"])

_admin_only = require_roles(MembershipRole.school_admin)


@router.get("/current", response_model=SchoolOut)
def current_school(
    ctx: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> SchoolOut:
    return SchoolOut.model_validate(school_service.get_school(db, ctx))


@router.get("/current/members", response_model=list[MemberOut])
def list_members(
    ctx: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)
) -> list[MemberOut]:
    return school_service.list_members(db, ctx)


@router.post("/current/members", response_model=MemberCreated, status_code=status.HTTP_201_CREATED)
def add_member(
    data: MemberCreate, ctx: TenantContext = Depends(_admin_only), db: Session = Depends(get_db)
) -> MemberCreated:
    """Add a member (creating the user if needed). A generated password is returned once."""
    return school_service.add_member(db, ctx, data)


@router.patch("/current/members/{membership_id}", response_model=MemberOut)
def update_member(
    membership_id: int,
    data: MemberRoleUpdate,
    ctx: TenantContext = Depends(_admin_only),
    db: Session = Depends(get_db),
) -> MemberOut:
    return school_service.update_member_role(db, ctx, membership_id, data.role)


@router.delete("/current/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    membership_id: int, ctx: TenantContext = Depends(_admin_only), db: Session = Depends(get_db)
) -> Response:
    school_service.remove_member(db, ctx, membership_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
