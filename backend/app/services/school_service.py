"""School info and membership management for the active school (tenant-scoped)."""

import logging
import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.auth.passwords import hash_password
from app.dependencies import TenantContext
from app.exceptions import ConflictError, NotFoundError
from app.models import Membership, MembershipRole, School, User
from app.schemas.schools import MemberCreate, MemberCreated, MemberOut
from app.services.audit import log_action

logger = logging.getLogger(__name__)


def get_school(db: Session, ctx: TenantContext) -> School:
    school = db.get(School, ctx.school_id)
    if school is None:
        raise NotFoundError("School")
    return school


def _to_member_out(m: Membership) -> MemberOut:
    return MemberOut(
        id=m.id,
        user_id=m.user_id,
        school_id=m.school_id,
        role=m.role,
        email=m.user.email,
        full_name=m.user.full_name,
        is_active=m.user.is_active,
        created_at=m.created_at,
    )


def list_members(db: Session, ctx: TenantContext) -> list[MemberOut]:
    rows = db.scalars(
        select(Membership)
        .join(Membership.user)
        .where(Membership.school_id == ctx.school_id)
        .options(joinedload(Membership.user))
        .order_by(func.lower(User.full_name), Membership.id)
    ).all()
    return [_to_member_out(m) for m in rows]


def _get_membership(db: Session, ctx: TenantContext, membership_id: int) -> Membership:
    m = db.scalar(
        select(Membership)
        .where(Membership.id == membership_id, Membership.school_id == ctx.school_id)
        .options(joinedload(Membership.user))
    )
    if m is None:
        raise NotFoundError("Member")
    return m


def _admin_count(db: Session, school_id: int) -> int:
    count = db.scalar(
        select(func.count(Membership.id)).where(
            Membership.school_id == school_id, Membership.role == MembershipRole.school_admin
        )
    )
    return count or 0


def add_member(db: Session, ctx: TenantContext, data: MemberCreate) -> MemberCreated:
    """Add a member; creates the user if needed (returns a one-time temporary password)."""
    user = db.scalar(select(User).where(User.email == data.email))
    temporary_password: str | None = None
    user_created = False
    if user is None:
        password = data.password
        if password is None:
            password = temporary_password = secrets.token_urlsafe(12)
        user = User(
            email=data.email,
            full_name=data.full_name,
            hashed_password=hash_password(password),
            is_active=True,
            is_superadmin=False,
        )
        db.add(user)
        db.flush()
        user_created = True
    else:
        existing = db.scalar(
            select(Membership.id).where(
                Membership.user_id == user.id, Membership.school_id == ctx.school_id
            )
        )
        if existing is not None:
            raise ConflictError("This user is already a member of the school")

    membership = Membership(user_id=user.id, school_id=ctx.school_id, role=data.role)
    db.add(membership)
    db.flush()
    log_action(
        db,
        school_id=ctx.school_id,
        user_id=ctx.user.id,
        actor="user",
        action="member.added",
        entity_type="membership",
        entity_id=membership.id,
        detail={"email": user.email, "role": data.role.value, "user_created": user_created},
    )
    db.commit()
    db.refresh(membership)
    logger.info("Member %s added to school %s", membership.id, ctx.school_id)
    base = _to_member_out(membership)
    return MemberCreated(
        **base.model_dump(), user_created=user_created, temporary_password=temporary_password
    )


def update_member_role(
    db: Session, ctx: TenantContext, membership_id: int, role: MembershipRole
) -> MemberOut:
    m = _get_membership(db, ctx, membership_id)
    old_role = m.role
    if old_role == role:
        return _to_member_out(m)
    if old_role == MembershipRole.school_admin and _admin_count(db, ctx.school_id) <= 1:
        raise ConflictError("A school must keep at least one school admin")
    m.role = role
    log_action(
        db,
        school_id=ctx.school_id,
        user_id=ctx.user.id,
        actor="user",
        action="member.role_changed",
        entity_type="membership",
        entity_id=m.id,
        detail={"email": m.user.email, "from": old_role.value, "to": role.value},
    )
    db.commit()
    return _to_member_out(m)


def remove_member(db: Session, ctx: TenantContext, membership_id: int) -> None:
    m = _get_membership(db, ctx, membership_id)
    if m.role == MembershipRole.school_admin and _admin_count(db, ctx.school_id) <= 1:
        raise ConflictError("Cannot remove the last school admin")
    log_action(
        db,
        school_id=ctx.school_id,
        user_id=ctx.user.id,
        actor="user",
        action="member.removed",
        entity_type="membership",
        entity_id=m.id,
        detail={"email": m.user.email, "role": m.role.value},
    )
    db.delete(m)
    db.commit()
