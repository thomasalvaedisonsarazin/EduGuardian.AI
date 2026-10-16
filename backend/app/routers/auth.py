"""Auth endpoints: register, login, refresh, logout, me."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth.rate_limit import rate_limit_auth
from app.dependencies import get_current_user, get_db
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_auth)],
)
def register(data: RegisterRequest, db: Session = Depends(get_db)) -> TokenPair:
    """Create a user and a new school; the caller becomes its school_admin."""
    return auth_service.register(db, data)


@router.post("/login", response_model=TokenPair, dependencies=[Depends(rate_limit_auth)])
def login(data: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    return auth_service.login(db, data)


@router.post("/refresh", response_model=TokenPair)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    """Exchange a refresh token for a new pair (the old refresh token is revoked)."""
    return auth_service.refresh(db, data.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(data: LogoutRequest, db: Session = Depends(get_db)) -> Response:
    auth_service.logout(db, data.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeResponse:
    me_out = MeResponse.model_validate(auth_service.get_me(db, user))
    me_out.memberships.sort(key=lambda m: m.school.name.lower())
    return me_out
