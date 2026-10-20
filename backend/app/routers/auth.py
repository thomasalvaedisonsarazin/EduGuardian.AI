"""Auth endpoints: register, login, refresh, logout, me.

Browsers get the refresh token as an httpOnly cookie (scoped to /api/v1/auth) so page scripts
never see it; API clients can keep sending it in the JSON body, which takes precedence.
"""

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.rate_limit import rate_limit_auth, rate_limit_login_account
from app.config import settings
from app.dependencies import get_current_user, get_db
from app.exceptions import ForbiddenError, UnauthorizedError
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

REFRESH_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, tokens: TokenPair) -> None:
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        tokens.refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
    )


def _refresh_token_from(
    request: Request, body: RefreshRequest | LogoutRequest | None
) -> str | None:
    if body is not None and body.refresh_token:
        return body.refresh_token
    return request.cookies.get(settings.REFRESH_COOKIE_NAME) or None


@router.post(
    "/register",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_auth)],
)
def register(data: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> TokenPair:
    """Create a user and a new school; the caller becomes its school_admin."""
    if not settings.ALLOW_REGISTRATION:
        raise ForbiddenError("New sign-ups are closed on this server", code="REGISTRATION_DISABLED")
    tokens = auth_service.register(db, data)
    _set_refresh_cookie(response, tokens)
    return tokens


@router.post("/login", response_model=TokenPair, dependencies=[Depends(rate_limit_auth)])
def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)) -> TokenPair:
    rate_limit_login_account(data.email)
    tokens = auth_service.login(db, data)
    _set_refresh_cookie(response, tokens)
    return tokens


@router.post("/refresh", response_model=TokenPair)
def refresh(
    request: Request,
    response: Response,
    data: RefreshRequest | None = None,
    db: Session = Depends(get_db),
) -> TokenPair:
    """Exchange a refresh token for a new pair (the old refresh token is revoked)."""
    raw = _refresh_token_from(request, data)
    if not raw:
        raise UnauthorizedError("No refresh token provided")
    tokens = auth_service.refresh(db, raw)
    _set_refresh_cookie(response, tokens)
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request, data: LogoutRequest | None = None, db: Session = Depends(get_db)
) -> Response:
    raw = _refresh_token_from(request, data)
    if raw:
        auth_service.logout(db, raw)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(response)
    return response


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeResponse:
    me_out = MeResponse.model_validate(auth_service.get_me(db, user))
    me_out.memberships.sort(key=lambda m: m.school.name.lower())
    return me_out
