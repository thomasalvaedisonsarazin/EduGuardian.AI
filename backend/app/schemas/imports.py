"""Pydantic schemas for the marks-import (Data Quality) endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import ImportStatus


class IssueOut(BaseModel):
    row: int | None = None
    column: str | None = None
    code: str
    severity: Literal["error", "warning"]
    message: str


class IssueSummary(BaseModel):
    errors: int = 0
    warnings: int = 0
    by_code: dict[str, int] = Field(default_factory=dict)


class ColumnMapOut(BaseModel):
    admission_column: str | None
    subjects: dict[str, int | None]


class ColumnMapUpdate(BaseModel):
    """PUT /imports/{id}/mapping body. Headers left out of ``subjects`` are unmapped."""

    admission_column: str | None
    subjects: dict[str, int | None] = Field(default_factory=dict)


class PreviewCell(BaseModel):
    subject_id: int
    raw: str
    value: str | None
    is_absent: bool


class PreviewRow(BaseModel):
    row: int
    admission_no: str
    student_id: int | None
    marks: dict[str, PreviewCell]


class ExamSubjectOut(BaseModel):
    id: int
    name: str
    code: str
    max_marks: Decimal
    pass_marks: Decimal


class ImportBatchListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    exam_id: int
    exam_name: str | None = None
    filename: str
    status: ImportStatus
    row_count: int
    summary: IssueSummary
    created_at: datetime


class ImportBatchDetail(ImportBatchListItem):
    column_map: ColumnMapOut
    headers: list[str]
    issues: list[IssueOut]
    summary_text: str
    preview: list[PreviewRow]
    can_commit: bool
    exam_subjects: list[ExamSubjectOut]
    uploaded_by: int | None


class CommitResult(BaseModel):
    batch_id: int
    inserted: int
    updated: int
    absent: int
    skipped: int
