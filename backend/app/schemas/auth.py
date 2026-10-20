"""Schemas for registration, login, token handling and the /auth/me profile."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import MembershipRole
from app.schemas.schools import SchoolOut


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    school_name: str = Field(min_length=2, max_length=200)
    school_code: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{2,50}$")

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("full_name", "school_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @field_validator("school_code", mode="before")
    @classmethod
    def _blank_code_is_none(cls, v: object) -> object:
        if isinstance(v, str) and not v.strip():
            return None
        return v.strip().upper() if isinstance(v, str) else v


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return v.strip().lower()


class RefreshRequest(BaseModel):
    """The refresh token may come in the body or (browsers) in the httpOnly refresh cookie."""

    refresh_token: str | None = Field(default=None, min_length=1, max_length=512)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=1, max_length=512)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class MembershipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    school_id: int
    role: MembershipRole
    school: SchoolOut


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    is_active: bool
    is_superadmin: bool
    created_at: datetime
    memberships: list[MembershipOut]
