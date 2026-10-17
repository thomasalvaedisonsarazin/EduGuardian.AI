"""Pydantic schemas for /interventions (review queue + approvals)."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import InterventionStatus


class ActivityIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=600)
    frequency: str = Field(min_length=1, max_length=80)
    owner: Literal["teacher", "student", "parent"]


class InterventionUpdate(BaseModel):
    """PUT body - only provided fields change; only allowed while the plan is a draft."""

    plan_text: str | None = Field(default=None, min_length=1, max_length=10_000)
    activities: list[ActivityIn] | None = Field(default=None, max_length=12)
    reassess_on: date | None = None


class RejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class StatusUpdate(BaseModel):
    status: Literal["in_progress", "completed"]
    note: str | None = Field(default=None, max_length=1000)


class StudentRef(BaseModel):
    id: int
    full_name: str
    pseudo_id: str
    admission_no: str
    class_section_id: int
    class_label: str


class InterventionOut(BaseModel):
    id: int
    run_id: int | None
    student: StudentRef
    subject_id: int | None
    subject_name: str | None
    status: InterventionStatus
    severity: str | None
    exam_id: int | None
    exam_name: str | None
    evidence: dict[str, Any] | None
    plan_text: str
    activities: list[dict[str, Any]]
    reassess_on: date | None
    approved_by: int | None
    approved_by_email: str | None
    approved_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
    can_review: bool


class InterventionList(BaseModel):
    items: list[InterventionOut]
    total: int
    counts: dict[str, int]
