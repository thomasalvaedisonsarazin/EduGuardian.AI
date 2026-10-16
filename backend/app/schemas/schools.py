"""Schemas for schools and school membership management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import MembershipRole


class SchoolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    code: str
    created_at: datetime


class MemberOut(BaseModel):
    """A membership row flattened with its user's public fields."""

    model_config = ConfigDict(from_attributes=True)

    id: int  # membership id
    user_id: int
    school_id: int
    role: MembershipRole
    email: str
    full_name: str
    is_active: bool
    created_at: datetime


class MemberCreated(MemberOut):
    """Response for adding a member; ``temporary_password`` is set (once) only when generated."""

    user_created: bool
    temporary_password: str | None = None


class MemberCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    role: MembershipRole
    password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("full_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("full_name must not be blank")
        return v


class MemberRoleUpdate(BaseModel):
    role: MembershipRole
