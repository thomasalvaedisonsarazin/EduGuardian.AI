"""Shared FastAPI dependencies.

Phase 2 (auth) replaces the stub bodies of `get_current_user` and `get_tenant_context`;
the signatures here are the contract routers depend on.
"""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import ForbiddenError, UnauthorizedError
from app.models import MembershipRole, User

__all__ = [
    "TenantContext",
    "get_current_user",
    "get_db",
    "get_tenant_context",
    "require_roles",
]


@dataclass(frozen=True)
class TenantContext:
    """The authenticated caller plus the active school (X-School-Id) and their role in it."""

    user: User
    school_id: int
    role: MembershipRole


def get_current_user(db: Session = Depends(get_db)) -> User:
    """Resolve the authenticated user from the bearer token. STUB - implemented in Phase 2."""
    raise UnauthorizedError("Authentication not implemented yet")


def get_tenant_context(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> TenantContext:
    """Verify the caller's membership in X-School-Id. STUB - implemented in Phase 2."""
    raise UnauthorizedError("Tenant resolution not implemented yet")


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
