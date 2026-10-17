"""Pydantic schemas for /audit-logs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    user_id: int | None
    user_email: str | None
    actor: str
    action: str
    entity_type: str
    entity_id: int | None
    detail: dict[str, Any] | None
    created_at: datetime


class AuditLogList(BaseModel):
    items: list[AuditLogOut]
    total: int
    actors: list[str]
    entity_types: list[str]
