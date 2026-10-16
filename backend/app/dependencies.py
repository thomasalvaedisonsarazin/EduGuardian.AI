"""Shared FastAPI dependencies.

`get_current_user` resolves the bearer access token; `get_tenant_context` resolves the active
school from the `X-School-Id` header and verifies the caller's membership. These signatures are
the contract routers depend on.
"""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token
from app.database import get_db
from app.exceptions import DomainValidationError, ForbiddenError, NotFoundError, UnauthorizedError
from app.models import Membership, MembershipRole, School, User

__all__ = [
    "TenantContext",
    "get_current_user",
    "get_db",
    "get_tenant_context",
    "require_roles",
]

SCHOOL_HEADER = "X-School-Id"

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class TenantContext:
    """The authenticated caller plus the active school (X-School-Id) and their role in it."""

    user: User
    school_id: int
    role: MembershipRole


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated, active user from the `Authorization: Bearer` access token."""
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise UnauthorizedError()
    user_id = decode_access_token(credentials.credentials)
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid access token")
    return user


def get_tenant_context(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_school_id: int | None = Header(default=None, alias=SCHOOL_HEADER),
) -> TenantContext:
    """Resolve the active school and the caller's role in it.

    - Header present -> caller must be a member (superadmins act as school_admin anywhere).
    - Header missing -> allowed only when the caller has exactly one membership.
    - Not a member -> 404 (never reveal that another school exists).
    """
    if x_school_id is None:
        memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).all()
        if len(memberships) == 1:
            only = memberships[0]
            return TenantContext(user=user, school_id=only.school_id, role=only.role)
        raise DomainValidationError(
            f"{SCHOOL_HEADER} header is required", code="SCHOOL_REQUIRED", status_code=400
        )

    membership = db.scalar(
        select(Membership).where(Membership.user_id == user.id, Membership.school_id == x_school_id)
    )
    if membership is not None:
        return TenantContext(user=user, school_id=membership.school_id, role=membership.role)
    if user.is_superadmin and db.get(School, x_school_id) is not None:
        return TenantContext(user=user, school_id=x_school_id, role=MembershipRole.school_admin)
    raise NotFoundError("School")


def require_roles(*roles: MembershipRole | str) -> Callable[..., TenantContext]:
    """Dependency factory: `ctx: TenantContext = Depends(require_roles(MembershipRole.teacher))`.

    No roles -> any member allowed. Superadmins bypass the role check.
    """
    allowed = {MembershipRole(r) for r in roles}

    def _checker(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if allowed and ctx.role not in allowed and not getattr(ctx.user, "is_superadmin", False):
            raise ForbiddenError()
        return ctx

    return _checker
