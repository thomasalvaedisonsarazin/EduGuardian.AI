"""Registration, login, refresh-token rotation and logout."""

import logging
import re
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth.jwt import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
)
from app.auth.passwords import DUMMY_HASH, hash_password, verify_password
from app.exceptions import ConflictError, UnauthorizedError
from app.models import Membership, MembershipRole, RefreshToken, School, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenPair
from app.services.audit import log_action

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS = "Invalid email or password"
INVALID_REFRESH = "Invalid or expired refresh token"
_CODE_MAX_LEN = 40


def _issue_tokens(db: Session, user: User) -> TokenPair:
    """Create an access JWT and persist a new (hashed) refresh token. Caller commits."""
    raw_refresh = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=refresh_token_expiry(),
            revoked=False,
        )
    )
    return TokenPair(access_token=create_access_token(user.id), refresh_token=raw_refresh)


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.strip().lower()))


def slugify_school_code(name: str) -> str:
    """'Green Valley High' -> 'GREEN-VALLEY-HIGH' (A-Z, 0-9, '-'), never empty."""
    slug = re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")
    return slug[:_CODE_MAX_LEN].rstrip("-") or "SCHOOL"


def generate_unique_school_code(db: Session, name: str) -> str:
    base = slugify_school_code(name)
    existing = set(db.scalars(select(School.code).where(School.code.like(f"{base}%"))).all())
    if base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"


def register(db: Session, data: RegisterRequest) -> TokenPair:
    """Create a user, a new school and a school_admin membership; return a token pair."""
    if get_user_by_email(db, data.email) is not None:
        raise ConflictError("An account with this email already exists")
    if data.school_code is not None:
        if db.scalar(select(School.id).where(School.code == data.school_code)) is not None:
            raise ConflictError("School code is already taken")
        code = data.school_code
    else:
        code = generate_unique_school_code(db, data.school_name)

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        is_active=True,
        is_superadmin=False,
    )
    school = School(name=data.school_name, code=code)
    db.add_all([user, school])
    try:
        db.flush()
        db.add(Membership(user_id=user.id, school_id=school.id, role=MembershipRole.school_admin))
        log_action(
            db,
            school_id=school.id,
            user_id=user.id,
            actor="user",
            action="school.registered",
            entity_type="school",
            entity_id=school.id,
            detail={"code": code},
        )
        tokens = _issue_tokens(db, user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.info("Registration conflict for %s: %s", data.email, exc.orig)
        raise ConflictError("Email or school code is already taken") from exc
    logger.info("Registered user %s with school %s", user.id, school.id)
    return tokens


def login(db: Session, data: LoginRequest) -> TokenPair:
    user = get_user_by_email(db, data.email)
    if user is None:
        verify_password(data.password, DUMMY_HASH)  # equalise timing
        raise UnauthorizedError(INVALID_CREDENTIALS)
    if not verify_password(data.password, user.hashed_password) or not user.is_active:
        raise UnauthorizedError(INVALID_CREDENTIALS)
    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


def _revoke_all(db: Session, user_id: int) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )


def _find_token(db: Session, raw_token: str) -> RefreshToken | None:
    return db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
    )


def refresh(db: Session, raw_token: str) -> TokenPair:
    """Rotate a refresh token. Reusing a revoked token revokes the user's whole session family."""
    stored = _find_token(db, raw_token)
    if stored is None:
        raise UnauthorizedError(INVALID_REFRESH)
    if stored.revoked:
        logger.warning("Refresh token reuse detected for user %s", stored.user_id)
        _revoke_all(db, stored.user_id)
        db.commit()
        raise UnauthorizedError(INVALID_REFRESH)
    expires_at = stored.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    user = db.get(User, stored.user_id)
    stored.revoked = True
    if expires_at <= datetime.now(UTC) or user is None or not user.is_active:
        db.commit()
        raise UnauthorizedError(INVALID_REFRESH)
    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


def logout(db: Session, raw_token: str) -> None:
    """Revoke a refresh token. Unknown tokens are ignored (idempotent)."""
    stored = _find_token(db, raw_token)
    if stored is not None and not stored.revoked:
        stored.revoked = True
        db.commit()


def get_me(db: Session, user: User) -> User:
    """Reload the user with memberships and their schools eagerly loaded ."""
    loaded = db.scalar(
        select(User)
        .where(User.id == user.id)
        .options(selectinload(User.memberships).selectinload(Membership.school))
        .execution_options(populate_existing=True)
    )
    if loaded is None:  # pragma: no cover - user deleted mid-request
        raise UnauthorizedError()
    return loaded
