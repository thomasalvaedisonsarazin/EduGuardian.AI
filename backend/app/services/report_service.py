"""Report service: permissions, listing, download and deletion around ``generate_report``.

Permission rules
----------------
* school_admin / principal / coordinator: any report kind for any scope in their school.
* teacher: no principal reports; class_teacher reports only for sections they teach
  (``TeachingAssignment`` via ``Teacher.user_id``); subject_teacher reports only for their own
  teacher record. Teachers see reports they created plus reports about their own teacher record
  or sections.
* delete: school_admin only (enforced by the router).

Foreign or invisible reports return 404.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.loader import get_class_section, get_exam
from app.dependencies import TenantContext
from app.exceptions import ForbiddenError, NotFoundError
from app.models import (
    AuditLog,
    MembershipRole,
    Report,
    ReportFormat,
    ReportKind,
    Teacher,
    TeachingAssignment,
    User,
)
from app.reports.generator import (
    AUDIT_ACTION_GENERATED,
    AUDIT_ENTITY,
    generate_report,
    remove_report_file,
    resolve_report_path,
)
from app.schemas.reports import ReportCreate, ReportOut
from app.services.audit import log_action

logger = logging.getLogger(__name__)

__all__ = [
    "MEDIA_TYPES",
    "ReportFile",
    "create_report",
    "delete_report",
    "get_report_file",
    "list_reports",
]

MEDIA_TYPES: dict[ReportFormat, str] = {
    ReportFormat.pdf: "application/pdf",
    ReportFormat.xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
KIND_LABELS: dict[ReportKind, str] = {
    ReportKind.principal: "Whole school",
    ReportKind.class_teacher: "Class",
    ReportKind.subject_teacher: "Teacher",
}
MAX_LIST = 200


@dataclass(frozen=True)
class ReportFile:
    path: Path
    filename: str
    media_type: str


@dataclass(frozen=True)
class _TeacherScope:
    teacher_ids: set[int]
    section_ids: set[int]


def _is_teacher(ctx: TenantContext) -> bool:
    return ctx.role == MembershipRole.teacher and not getattr(ctx.user, "is_superadmin", False)


def _teacher_scope(db: Session, ctx: TenantContext) -> _TeacherScope:
    teacher_ids = set(
        db.scalars(
            select(Teacher.id).where(
                Teacher.school_id == ctx.school_id, Teacher.user_id == ctx.user.id
            )
        )
    )
    section_ids: set[int] = set()
    if teacher_ids:
        section_ids = set(
            db.scalars(
                select(TeachingAssignment.class_section_id).where(
                    TeachingAssignment.school_id == ctx.school_id,
                    TeachingAssignment.teacher_id.in_(teacher_ids),
                )
            )
        )
    return _TeacherScope(teacher_ids=teacher_ids, section_ids=section_ids)


def _check_generate_permission(db: Session, ctx: TenantContext, data: ReportCreate) -> None:
    """404 for foreign ids first, then 403 when a teacher asks for someone else's scope."""
    get_exam(db, ctx.school_id, data.exam_id)
    if data.kind == ReportKind.class_teacher and data.class_section_id is not None:
        get_class_section(db, ctx.school_id, data.class_section_id)
    if data.kind == ReportKind.subject_teacher and data.teacher_id is not None:
        teacher = db.scalar(
            select(Teacher).where(Teacher.id == data.teacher_id, Teacher.school_id == ctx.school_id)
        )
        if teacher is None:
            raise NotFoundError("Teacher")
    if not _is_teacher(ctx):
        return
    scope = _teacher_scope(db, ctx)
    if data.kind == ReportKind.principal:
        raise ForbiddenError("Teachers cannot generate principal reports")
    if data.kind == ReportKind.class_teacher and data.class_section_id not in scope.section_ids:
        raise ForbiddenError("You can only generate reports for classes you teach")
    if data.kind == ReportKind.subject_teacher and data.teacher_id not in scope.teacher_ids:
        raise ForbiddenError("You can only generate your own subject teacher report")


def _metadata(db: Session, school_id: int, report_ids: list[int]) -> dict[int, dict[str, Any]]:
    if not report_ids:
        return {}
    rows = db.scalars(
        select(AuditLog)
        .where(
            AuditLog.school_id == school_id,
            AuditLog.entity_type == AUDIT_ENTITY,
            AuditLog.action == AUDIT_ACTION_GENERATED,
            AuditLog.entity_id.in_(report_ids),
        )
        .order_by(AuditLog.id)
    ).all()
    return {row.entity_id: dict(row.detail or {}) for row in rows if row.entity_id is not None}


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _to_out(report: Report, meta: dict[str, Any], creator: str | None) -> ReportOut:
    file_name = Path(report.file_path).name
    return ReportOut(
        id=report.id,
        school_id=report.school_id,
        run_id=report.run_id,
        kind=report.kind,
        format=report.format,
        exam_id=_int_or_none(meta.get("exam_id")),
        exam_name=meta.get("exam_name"),
        class_section_id=_int_or_none(meta.get("class_section_id")),
        teacher_id=_int_or_none(meta.get("teacher_id")),
        scope_label=str(meta.get("scope_label") or KIND_LABELS[ReportKind(report.kind)]),
        file_name=file_name,
        size_bytes=_int_or_none(meta.get("size_bytes")),
        created_by=report.created_by,
        created_by_name=creator,
        created_at=report.created_at,
        download_url=f"/api/v1/reports/{report.id}/download",
    )


def _visible_to_teacher(
    report: Report, meta: dict[str, Any], ctx: TenantContext, scope: _TeacherScope
) -> bool:
    if report.created_by == ctx.user.id:
        return True
    if report.kind == ReportKind.subject_teacher:
        return _int_or_none(meta.get("teacher_id")) in scope.teacher_ids
    if report.kind == ReportKind.class_teacher:
        return _int_or_none(meta.get("class_section_id")) in scope.section_ids
    return False


def _creator_names(db: Session, user_ids: set[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = db.execute(select(User.id, User.full_name).where(User.id.in_(user_ids))).all()
    return {int(uid): str(name) for uid, name in rows}


def _serialize(db: Session, ctx: TenantContext, reports: list[Report]) -> list[ReportOut]:
    meta = _metadata(db, ctx.school_id, [r.id for r in reports])
    names = _creator_names(db, {r.created_by for r in reports if r.created_by is not None})
    return [
        _to_out(r, meta.get(r.id, {}), names.get(r.created_by) if r.created_by else None)
        for r in reports
    ]


def create_report(db: Session, ctx: TenantContext, data: ReportCreate) -> ReportOut:
    """Check permissions, generate the report and commit."""
    _check_generate_permission(db, ctx, data)
    report: Report | None = None
    try:
        report = generate_report(
            db,
            school_id=ctx.school_id,
            kind=data.kind,
            fmt=data.format,
            exam_id=data.exam_id,
            class_section_id=data.class_section_id,
            teacher_id=data.teacher_id,
            created_by=ctx.user.id,
        )
        db.commit()
    except Exception:
        orphan = (
            Report(school_id=report.school_id, file_path=report.file_path)
            if report is not None
            else None
        )
        db.rollback()
        if orphan is not None:
            remove_report_file(orphan)
        raise
    db.refresh(report)
    return _serialize(db, ctx, [report])[0]


def list_reports(
    db: Session,
    ctx: TenantContext,
    *,
    exam_id: int | None = None,
    kind: ReportKind | None = None,
    run_id: int | None = None,
    limit: int = MAX_LIST,
) -> list[ReportOut]:
    """Reports of the school, newest first, filtered and restricted to what the caller may see."""
    stmt = select(Report).where(Report.school_id == ctx.school_id)
    if kind is not None:
        stmt = stmt.where(Report.kind == kind)
    if run_id is not None:
        stmt = stmt.where(Report.run_id == run_id)
    reports = list(db.scalars(stmt.order_by(Report.created_at.desc(), Report.id.desc())).all())
    meta = _metadata(db, ctx.school_id, [r.id for r in reports])
    if exam_id is not None:
        reports = [r for r in reports if _int_or_none(meta.get(r.id, {}).get("exam_id")) == exam_id]
    if _is_teacher(ctx):
        scope = _teacher_scope(db, ctx)
        reports = [r for r in reports if _visible_to_teacher(r, meta.get(r.id, {}), ctx, scope)]
    reports = reports[: max(1, min(limit, MAX_LIST))]
    names = _creator_names(db, {r.created_by for r in reports if r.created_by is not None})
    return [
        _to_out(r, meta.get(r.id, {}), names.get(r.created_by) if r.created_by else None)
        for r in reports
    ]


def _get_visible(db: Session, ctx: TenantContext, report_id: int) -> Report:
    report = db.scalar(
        select(Report).where(Report.id == report_id, Report.school_id == ctx.school_id)
    )
    if report is None:
        raise NotFoundError("Report")
    if _is_teacher(ctx):
        meta = _metadata(db, ctx.school_id, [report.id]).get(report.id, {})
        if not _visible_to_teacher(report, meta, ctx, _teacher_scope(db, ctx)):
            raise NotFoundError("Report")
    return report


def get_report_file(db: Session, ctx: TenantContext, report_id: int) -> ReportFile:
    """Resolve a report's file for download (path-traversal safe)."""
    report = _get_visible(db, ctx, report_id)
    path = resolve_report_path(report)
    if not path.is_file():
        logger.warning("Report file missing: report=%s path=%s", report.id, report.file_path)
        raise NotFoundError("Report file")
    return ReportFile(
        path=path,
        filename=path.name,
        media_type=MEDIA_TYPES[ReportFormat(report.format)],
    )


def delete_report(db: Session, ctx: TenantContext, report_id: int) -> None:
    """Delete the file and the row; audit-logged."""
    report = _get_visible(db, ctx, report_id)
    removed = remove_report_file(report)
    log_action(
        db,
        school_id=ctx.school_id,
        actor="user",
        action="report.deleted",
        entity_type=AUDIT_ENTITY,
        entity_id=report.id,
        user_id=ctx.user.id,
        detail={
            "kind": ReportKind(report.kind).value,
            "format": ReportFormat(report.format).value,
            "file_removed": removed,
        },
    )
    db.delete(report)
    db.commit()
    logger.info("Report deleted id=%s school=%s by user=%s", report_id, ctx.school_id, ctx.user.id)
