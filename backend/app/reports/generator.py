"""Reporting Agent entry point: build a report's content, render it and record the Report row.

Contract (called by the Module 5 orchestrator's Reporting node and by ``/api/v1/reports``)::

    generate_report(db, *, school_id, kind, fmt, exam_id, class_section_id=None,
                    teacher_id=None, run_id=None, created_by=None) -> Report

The file is written to ``settings.REPORTS_DIR/<school_id>/<report_id>_<kind>_<exam-slug>.<ext>``;
``Report.file_path`` is stored relative to ``REPORTS_DIR``. The Report row and an AuditLog entry
(actor ``ReportingAgent``) are added and flushed - the caller commits (or rolls back, in which
case the caller should also remove the file; see :func:`remove_report_file`).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.loader import class_label, get_class_section, get_exam
from app.analytics.service import ExamOverview, exam_overview, teacher_view
from app.config import settings
from app.exceptions import DomainValidationError, NotFoundError
from app.models import (
    AgentRun,
    ClassSection,
    InterventionPlan,
    Report,
    ReportFormat,
    ReportKind,
    School,
    Student,
    Subject,
)
from app.reports.content import (
    PlanRow,
    ReportContent,
    build_class_teacher_content,
    build_principal_content,
    build_subject_teacher_content,
)
from app.reports.pdf import render_pdf
from app.reports.xlsx import render_xlsx
from app.services.audit import log_action

logger = logging.getLogger(__name__)

__all__ = [
    "REPORTING_AGENT",
    "generate_report",
    "load_exam_plans",
    "remove_report_file",
    "report_meta",
    "resolve_report_path",
    "school_reports_dir",
    "slugify",
]

REPORTING_AGENT = "ReportingAgent"
AUDIT_ACTION_GENERATED = "report.generated"
AUDIT_ENTITY = "report"
PENDING_PATH = "pending"


def slugify(value: str, max_length: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:max_length].strip("-") or "exam"


def reports_root() -> Path:
    return Path(settings.REPORTS_DIR).resolve()


def school_reports_dir(school_id: int) -> Path:
    return reports_root() / str(int(school_id))


def resolve_report_path(report: Report) -> Path:
    """Absolute path of a report's file, guaranteed to live under REPORTS_DIR/<school_id>.

    Raises ``NotFoundError`` for paths that escape the school's directory (path traversal).
    """
    base = school_reports_dir(report.school_id)
    target = (reports_root() / report.file_path).resolve()
    if not target.is_relative_to(base) or target == base:
        logger.warning("Rejected report path outside school dir: report=%s", report.id)
        raise NotFoundError("Report file")
    return target


def remove_report_file(report: Report) -> bool:
    """Delete a report's file if present. Returns True when a file was removed."""
    try:
        path = resolve_report_path(report)
    except NotFoundError:
        return False
    if path.is_file():
        path.unlink()
        return True
    return False


def load_exam_plans(
    db: Session, school_id: int, exam_id: int, student_ids: Sequence[int] | None = None
) -> list[PlanRow]:
    """Intervention plans linked to an exam (via the run's input or the plan's evidence)."""
    stmt = (
        select(InterventionPlan, Student, ClassSection, Subject, AgentRun)
        .join(Student, Student.id == InterventionPlan.student_id)
        .join(ClassSection, ClassSection.id == Student.class_section_id)
        .outerjoin(Subject, Subject.id == InterventionPlan.subject_id)
        .outerjoin(AgentRun, AgentRun.id == InterventionPlan.run_id)
        .where(InterventionPlan.school_id == school_id, Student.school_id == school_id)
        .order_by(InterventionPlan.id)
    )
    if student_ids is not None:
        if not student_ids:
            return []
        stmt = stmt.where(InterventionPlan.student_id.in_(list(student_ids)))
    rows: list[PlanRow] = []
    for plan, student, section, subject, run in db.execute(stmt).all():
        if not _plan_matches_exam(plan, run, exam_id):
            continue
        rows.append(
            PlanRow(
                plan_id=plan.id,
                student_id=student.id,
                pseudo_id=student.pseudo_id,
                full_name=student.full_name,
                class_label=class_label(section),
                subject_name=subject.name if subject is not None else None,
                status=str(plan.status.value if hasattr(plan.status, "value") else plan.status),
                plan_text=plan.plan_text or "",
                reassess_on=plan.reassess_on,
                run_id=plan.run_id,
            )
        )
    return rows


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _plan_matches_exam(plan: InterventionPlan, run: AgentRun | None, exam_id: int) -> bool:
    evidence = plan.evidence if isinstance(plan.evidence, dict) else {}
    if _as_int(evidence.get("exam_id")) == exam_id:
        return True
    run_input = run.input if run is not None and isinstance(run.input, dict) else {}
    return _as_int(run_input.get("exam_id")) == exam_id


def _previous_overview(
    db: Session, school_id: int, overview: ExamOverview, section_ids: list[int] | None
) -> ExamOverview | None:
    if overview.comparison_exam_id is None:
        return None
    return exam_overview(db, school_id, overview.comparison_exam_id, section_ids)


def _validate_combo(kind: ReportKind, class_section_id: int | None, teacher_id: int | None) -> None:
    if kind == ReportKind.class_teacher and class_section_id is None:
        raise DomainValidationError("A class teacher report needs class_section_id")
    if kind == ReportKind.subject_teacher and teacher_id is None:
        raise DomainValidationError("A subject teacher report needs teacher_id")


def _build_content(
    db: Session,
    *,
    school: School,
    kind: ReportKind,
    exam_id: int,
    class_section_id: int | None,
    teacher_id: int | None,
    generated_at: datetime,
) -> ReportContent:
    if kind == ReportKind.principal:
        overview = exam_overview(db, school.id, exam_id)
        plans = load_exam_plans(db, school.id, exam_id, [r.student_id for r in overview.results])
        return build_principal_content(
            school_name=school.name,
            overview=overview,
            previous=_previous_overview(db, school.id, overview, None),
            plans=plans,
            generated_at=generated_at,
        )
    if kind == ReportKind.class_teacher:
        assert class_section_id is not None
        section = get_class_section(db, school.id, class_section_id)
        overview = exam_overview(db, school.id, exam_id, [section.id])
        plans = load_exam_plans(db, school.id, exam_id, [r.student_id for r in overview.results])
        return build_class_teacher_content(
            school_name=school.name,
            overview=overview,
            previous=_previous_overview(db, school.id, overview, [section.id]),
            class_label=class_label(section),
            plans=plans,
            generated_at=generated_at,
        )
    assert teacher_id is not None
    view = teacher_view(db, school.id, teacher_id, exam_id)
    return build_subject_teacher_content(
        school_name=school.name, view=view, generated_at=generated_at
    )


def report_meta(
    *,
    kind: ReportKind,
    fmt: ReportFormat,
    exam_id: int,
    exam_name: str,
    class_section_id: int | None,
    teacher_id: int | None,
    scope_label: str,
    run_id: int | None,
) -> dict[str, Any]:
    """Metadata stored in the generation audit entry (Report has no exam/scope columns)."""
    return {
        "kind": kind.value,
        "format": fmt.value,
        "exam_id": exam_id,
        "exam_name": exam_name,
        "class_section_id": class_section_id if kind == ReportKind.class_teacher else None,
        "teacher_id": teacher_id if kind == ReportKind.subject_teacher else None,
        "scope_label": scope_label,
        "run_id": run_id,
    }


def generate_report(
    db: Session,
    *,
    school_id: int,
    kind: ReportKind,
    fmt: ReportFormat,
    exam_id: int,
    class_section_id: int | None = None,
    teacher_id: int | None = None,
    run_id: int | None = None,
    created_by: int | None = None,
) -> Report:
    """Build, render and register a report. Adds + flushes the Report row; caller commits.

    Raises ``DomainValidationError`` (422) for invalid kind/parameter combinations and
    ``NotFoundError`` (404) for ids that do not belong to the school.
    """
    try:
        kind = ReportKind(kind)
        fmt = ReportFormat(fmt)
    except ValueError as exc:
        raise DomainValidationError(f"Unsupported report kind or format: {exc}") from exc
    _validate_combo(kind, class_section_id, teacher_id)

    school = db.get(School, school_id)
    if school is None:
        raise NotFoundError("School")
    exam = get_exam(db, school_id, exam_id)
    if run_id is not None:
        run = db.get(AgentRun, run_id)
        if run is None or run.school_id != school_id:
            raise NotFoundError("Agent run")

    generated_at = datetime.now(UTC)
    content = _build_content(
        db,
        school=school,
        kind=kind,
        exam_id=exam.id,
        class_section_id=class_section_id,
        teacher_id=teacher_id,
        generated_at=generated_at,
    )

    report = Report(
        school_id=school_id,
        run_id=run_id,
        kind=kind,
        format=fmt,
        file_path=PENDING_PATH,
        created_by=created_by,
    )
    db.add(report)
    db.flush()

    file_name = f"{report.id}_{kind.value}_{slugify(exam.name)}.{fmt.value}"
    directory = school_reports_dir(school_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / file_name
    try:
        if fmt == ReportFormat.pdf:
            render_pdf(content, path)
        else:
            render_xlsx(content, path)
    except Exception:
        logger.exception("Rendering report %s failed", report.id)
        path.unlink(missing_ok=True)
        raise
    report.file_path = f"{school_id}/{file_name}"
    db.flush()

    detail = report_meta(
        kind=kind,
        fmt=fmt,
        exam_id=exam.id,
        exam_name=exam.name,
        class_section_id=class_section_id,
        teacher_id=teacher_id,
        scope_label=content.scope_label,
        run_id=run_id,
    )
    detail["file_name"] = file_name
    detail["size_bytes"] = path.stat().st_size
    log_action(
        db,
        school_id=school_id,
        actor=REPORTING_AGENT,
        action=AUDIT_ACTION_GENERATED,
        entity_type=AUDIT_ENTITY,
        entity_id=report.id,
        user_id=created_by,
        detail=detail,
    )
    db.flush()
    logger.info(
        "Report generated id=%s school=%s kind=%s format=%s exam=%s run=%s",
        report.id,
        school_id,
        kind.value,
        fmt.value,
        exam.id,
        run_id,
    )
    return report
