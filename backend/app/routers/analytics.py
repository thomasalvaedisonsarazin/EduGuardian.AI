"""Analytics endpoints (Module 4): deterministic exam, class, subject, student and teacher views.

All endpoints are available to any member of the active school and are tenant-scoped: ids
belonging to another school return 404.
"""

import logging
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics import service
from app.analytics.calculations import class_summary, to_jsonable
from app.analytics.loader import class_label, get_class_section
from app.dependencies import TenantContext, get_db, require_roles
from app.exceptions import DomainValidationError, NotFoundError
from app.models import Subject
from app.schemas.analytics import (
    AtRiskResponse,
    ClassAnalyticsResponse,
    DashboardOverviewResponse,
    ExamListItemOut,
    ExamSummaryResponse,
    StudentTrendResponse,
    SubjectAnalyticsResponse,
    TeacherViewResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])

_member = require_roles()


def parse_section_ids(raw: str | None) -> list[int] | None:
    """Parse ``?class_section_ids=1,2`` into ``[1, 2]`` (None when absent/empty)."""
    if raw is None or not raw.strip():
        return None
    try:
        ids = sorted({int(part) for part in raw.split(",") if part.strip()})
    except ValueError as exc:
        raise DomainValidationError("class_section_ids must be comma-separated integers") from exc
    return ids or None


def _section_ids(
    class_section_ids: str | None = Query(
        default=None, description="Comma-separated class section ids, e.g. 1,2"
    ),
) -> list[int] | None:
    return parse_section_ids(class_section_ids)


def _j(value: Any) -> Any:
    return to_jsonable(value)


@router.get("/overview", response_model=DashboardOverviewResponse)
def overview(
    ctx: TenantContext = Depends(_member), db: Session = Depends(get_db)
) -> DashboardOverviewResponse:
    """Dashboard: latest exam with marks, headline numbers, at-risk preview and trend."""
    result = service.dashboard_overview(db, ctx.school_id)
    return DashboardOverviewResponse.model_validate(result.to_dict())


@router.get("/exams", response_model=list[ExamListItemOut])
def list_exams(
    ctx: TenantContext = Depends(_member), db: Session = Depends(get_db)
) -> list[ExamListItemOut]:
    """Exams of the school (oldest first) with their recorded mark counts."""
    return [
        ExamListItemOut.model_validate(item.to_dict())
        for item in service.list_exams(db, ctx.school_id)
    ]


@router.get("/exams/{exam_id}/summary", response_model=ExamSummaryResponse)
def exam_summary(
    exam_id: int,
    class_section_ids: list[int] | None = Depends(_section_ids),
    ctx: TenantContext = Depends(_member),
    db: Session = Depends(get_db),
) -> ExamSummaryResponse:
    ov = service.exam_overview(db, ctx.school_id, exam_id, class_section_ids)
    return ExamSummaryResponse.model_validate(
        {
            "exam": _j(ov.exam),
            "previous_exam": _j(ov.previous_exam),
            "comparison_exam_id": ov.comparison_exam_id,
            "class_section_ids": ov.class_section_ids,
            "subjects": _j(ov.subjects),
            "school_summary": _j(ov.school_summary),
            "class_summaries": _j(ov.class_summaries),
            "subject_summaries": _j(ov.subject_summaries),
            "at_risk_count": len(ov.at_risk),
            "at_risk_high_count": sum(1 for a in ov.at_risk if a.severity == "high"),
            "at_risk": _j(ov.at_risk),
        }
    )


@router.get("/exams/{exam_id}/classes/{class_id}", response_model=ClassAnalyticsResponse)
def exam_class(
    exam_id: int,
    class_id: int,
    ctx: TenantContext = Depends(_member),
    db: Session = Depends(get_db),
) -> ClassAnalyticsResponse:
    section = get_class_section(db, ctx.school_id, class_id)
    label = class_label(section)
    ov = service.exam_overview(db, ctx.school_id, exam_id, [class_id])
    summary = ov.class_summaries[0] if ov.class_summaries else class_summary([], class_id, label)
    return ClassAnalyticsResponse.model_validate(
        {
            "exam": _j(ov.exam),
            "previous_exam": _j(ov.previous_exam),
            "class_section_id": class_id,
            "class_label": label,
            "summary": _j(summary),
            "subjects": _j(ov.subjects),
            "subject_summaries": _j(ov.subject_summaries),
            "results": _j(ov.results),
            "changes": _j(ov.changes),
            "at_risk": _j(ov.at_risk),
        }
    )


@router.get("/exams/{exam_id}/subjects/{subject_id}", response_model=SubjectAnalyticsResponse)
def exam_subject(
    exam_id: int,
    subject_id: int,
    class_section_ids: list[int] | None = Depends(_section_ids),
    ctx: TenantContext = Depends(_member),
    db: Session = Depends(get_db),
) -> SubjectAnalyticsResponse:
    exists = db.scalar(
        select(Subject.id).where(Subject.id == subject_id, Subject.school_id == ctx.school_id)
    )
    if exists is None:
        raise NotFoundError("Subject")
    ov = service.exam_overview(db, ctx.school_id, exam_id, class_section_ids)
    summary = next((s for s in ov.subject_summaries if s.subject_id == subject_id), None)
    if summary is None:
        raise NotFoundError(message="Subject is not configured for this exam")

    rows: list[dict[str, Any]] = []
    for r in ov.results:
        entry = r.subject(subject_id)
        if entry is None:
            continue
        delta: Decimal | None = None
        change = ov.change_for(r.student_id)
        if change is not None:
            delta = next((s.delta for s in change.subjects if s.subject_id == subject_id), None)
        rows.append(
            {
                "student_id": r.student_id,
                "pseudo_id": r.pseudo_id,
                "full_name": r.full_name,
                "class_section_id": r.class_section_id,
                "class_label": r.class_label,
                "marks": entry.marks,
                "is_absent": entry.is_absent,
                "is_missing": entry.is_missing,
                "passed": entry.passed,
                "percentage": entry.percentage,
                "delta": delta,
            }
        )
    return SubjectAnalyticsResponse.model_validate(
        {
            "exam": _j(ov.exam),
            "previous_exam": _j(ov.previous_exam),
            "summary": _j(summary),
            "students": rows,
        }
    )


@router.get("/exams/{exam_id}/at-risk", response_model=AtRiskResponse)
def exam_at_risk(
    exam_id: int,
    class_section_ids: list[int] | None = Depends(_section_ids),
    ctx: TenantContext = Depends(_member),
    db: Session = Depends(get_db),
) -> AtRiskResponse:
    ov = service.exam_overview(db, ctx.school_id, exam_id, class_section_ids)
    return AtRiskResponse.model_validate(
        {
            "exam": _j(ov.exam),
            "previous_exam": _j(ov.previous_exam),
            "count": len(ov.at_risk),
            "high_count": sum(1 for a in ov.at_risk if a.severity == "high"),
            "students": _j(ov.at_risk),
        }
    )


@router.get("/students/{student_id}/trend", response_model=StudentTrendResponse)
def student_trend(
    student_id: int,
    ctx: TenantContext = Depends(_member),
    db: Session = Depends(get_db),
) -> StudentTrendResponse:
    trend = service.student_trend(db, ctx.school_id, student_id)
    return StudentTrendResponse.model_validate(trend.to_dict())


@router.get("/teachers/{teacher_id}", response_model=TeacherViewResponse)
def teacher_insights(
    teacher_id: int,
    exam_id: int = Query(..., description="Exam to analyse"),
    ctx: TenantContext = Depends(_member),
    db: Session = Depends(get_db),
) -> TeacherViewResponse:
    """Coaching view of a teacher's classes for one exam (no teacher score or ranking)."""
    view = service.teacher_view(db, ctx.school_id, teacher_id, exam_id)
    return TeacherViewResponse.model_validate(view.to_dict())
