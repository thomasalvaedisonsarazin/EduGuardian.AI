"""Request/response schemas for /api/v1/reports."""

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import ReportFormat, ReportKind


class ReportCreate(BaseModel):
    """Generate a report.

    class_teacher needs ``class_section_id``; subject_teacher needs ``teacher_id``.
    """

    model_config = ConfigDict(populate_by_name=True)

    kind: ReportKind
    format: ReportFormat = ReportFormat.pdf
    exam_id: int = Field(gt=0)
    class_section_id: int | None = Field(default=None, gt=0)
    teacher_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _check_scope(self) -> Self:
        if self.kind == ReportKind.class_teacher and self.class_section_id is None:
            raise ValueError("class_section_id is required for a class teacher report")
        if self.kind == ReportKind.subject_teacher and self.teacher_id is None:
            raise ValueError("teacher_id is required for a subject teacher report")
        return self


class ReportOut(BaseModel):
    """Report metadata. Exam/scope details come from the generation audit entry."""

    id: int
    school_id: int
    run_id: int | None
    kind: ReportKind
    format: ReportFormat
    exam_id: int | None
    exam_name: str | None
    class_section_id: int | None
    teacher_id: int | None
    scope_label: str
    file_name: str
    size_bytes: int | None
    created_by: int | None
    created_by_name: str | None
    created_at: datetime
    download_url: str
