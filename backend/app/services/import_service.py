"""Marks import workflow: upload -> validate (Data Quality Agent) -> remap -> commit/reject.

ImportBatch JSON columns:
- ``column_map``: ``{"admission_column", "subjects": {header: subject_id|null}, "headers": [...]}``
- ``issues``: list of Issue dicts (see ``app.agents.data_quality.Issue.to_dict``)
- ``preview``: every normalized row (``NormalizedRow.to_dict``); the detail view returns 50.
"""

import csv
import io
import logging
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import data_quality as dq
from app.config import settings
from app.dependencies import TenantContext
from app.exceptions import ConflictError, DomainValidationError, ForbiddenError, NotFoundError
from app.models import (
    ClassSection,
    Exam,
    ExamSubjectConfig,
    ImportBatch,
    ImportStatus,
    Mark,
    MembershipRole,
    Student,
    Subject,
    Teacher,
    TeachingAssignment,
)
from app.schemas.imports import (
    ColumnMapOut,
    ColumnMapUpdate,
    CommitResult,
    ExamSubjectOut,
    ImportBatchDetail,
    ImportBatchListItem,
    IssueOut,
    IssueSummary,
    PreviewRow,
)
from app.services.audit import log_action

logger = logging.getLogger(__name__)

PREVIEW_LIMIT = 50
LIST_LIMIT = 100


@dataclass(frozen=True)
class ExamSubject:
    subject: Subject
    config: ExamSubjectConfig


# --- lookups -------------------------------------------------------------------------------
def get_exam(db: Session, school_id: int, exam_id: int) -> Exam:
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id))
    if exam is None:
        raise NotFoundError("Exam")
    return exam


def get_batch(db: Session, school_id: int, batch_id: int) -> ImportBatch:
    batch = db.scalar(
        select(ImportBatch).where(ImportBatch.id == batch_id, ImportBatch.school_id == school_id)
    )
    if batch is None:
        raise NotFoundError("Import batch")
    return batch


# --- teacher scope -------------------------------------------------------------------------
def is_restricted_teacher(ctx: TenantContext) -> bool:
    """Teachers may only see their own batches and write marks for what they teach."""
    return ctx.role == MembershipRole.teacher and not getattr(ctx.user, "is_superadmin", False)


def teacher_assignment_pairs(db: Session, ctx: TenantContext) -> set[tuple[int, int]]:
    """``(class_section_id, subject_id)`` pairs the caller teaches in the active school."""
    rows = db.execute(
        select(TeachingAssignment.class_section_id, TeachingAssignment.subject_id)
        .join(Teacher, Teacher.id == TeachingAssignment.teacher_id)
        .where(
            Teacher.user_id == ctx.user.id,
            Teacher.school_id == ctx.school_id,
            TeachingAssignment.school_id == ctx.school_id,
        )
    ).all()
    return {(int(section_id), int(subject_id)) for section_id, subject_id in rows}


def get_visible_batch(db: Session, ctx: TenantContext, batch_id: int) -> ImportBatch:
    """Tenant-scoped batch; teachers only see batches they uploaded (others -> 404)."""
    batch = get_batch(db, ctx.school_id, batch_id)
    if is_restricted_teacher(ctx) and batch.uploaded_by != ctx.user.id:
        raise NotFoundError("Import batch")
    return batch


def _check_teacher_write_scope(
    db: Session, ctx: TenantContext, rows: list[dict[str, Any]], allowed_subjects: set[int]
) -> None:
    """403 when a teacher's import would write marks outside their teaching assignments."""
    if not is_restricted_teacher(ctx):
        return
    pairs = teacher_assignment_pairs(db, ctx)
    student_ids = {int(r["student_id"]) for r in rows if r.get("student_id") is not None}
    sections = dict(
        db.execute(
            select(Student.id, Student.class_section_id).where(
                Student.school_id == ctx.school_id, Student.id.in_(student_ids)
            )
        ).all()
    )
    outside = 0
    for row in rows:
        student_id = row.get("student_id")
        if student_id is None:
            continue
        section_id = sections.get(int(student_id))
        for cell in (row.get("marks") or {}).values():
            subject_id = int(cell["subject_id"])
            if subject_id not in allowed_subjects:
                continue
            if not cell.get("is_absent") and cell.get("value") is None:
                continue  # blank cells are never written
            if (section_id, subject_id) not in pairs:
                outside += 1
    if outside:
        raise ForbiddenError(
            f"You can only import marks for the classes and subjects you teach "
            f"({outside} mark(s) are outside your teaching assignments)"
        )


def exam_subjects(db: Session, school_id: int, exam_id: int) -> list[ExamSubject]:
    rows = db.execute(
        select(Subject, ExamSubjectConfig)
        .join(ExamSubjectConfig, ExamSubjectConfig.subject_id == Subject.id)
        .where(
            ExamSubjectConfig.exam_id == exam_id,
            ExamSubjectConfig.school_id == school_id,
            Subject.school_id == school_id,
        )
        .order_by(Subject.name)
    ).all()
    return [ExamSubject(subject=s, config=c) for s, c in rows]


def exam_students(db: Session, school_id: int, exam: Exam) -> list[Student]:
    """Students of the exam's academic year, ordered by grade/section/admission number."""
    return list(
        db.scalars(
            select(Student)
            .join(ClassSection, ClassSection.id == Student.class_section_id)
            .where(
                Student.school_id == school_id,
                ClassSection.school_id == school_id,
                ClassSection.academic_year_id == exam.academic_year_id,
            )
            .order_by(ClassSection.grade, ClassSection.section, Student.admission_no)
        )
    )


# --- file storage --------------------------------------------------------------------------
def safe_filename(filename: str) -> str:
    base = Path(filename.replace("\\", "/")).name or "upload"
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base).strip("._") or "upload"
    return cleaned[-120:]


def batch_file_path(batch: ImportBatch) -> Path:
    return (
        Path(settings.UPLOADS_DIR)
        / str(batch.school_id)
        / f"{batch.id}_{safe_filename(batch.filename)}"
    )


def _read_batch_file(batch: ImportBatch) -> bytes:
    path = batch_file_path(batch)
    if not path.is_file():
        raise ConflictError("The uploaded file is no longer available - upload it again")
    return path.read_bytes()


# --- validation ----------------------------------------------------------------------------
def _run_validation(
    db: Session, school_id: int, exam: Exam, sheet: dq.ParsedSheet, column_map: dq.ColumnMap
) -> dq.ValidationResult:
    subjects = exam_subjects(db, school_id, exam.id)
    roster = {
        s.admission_no: dq.StudentRef(
            id=s.id, admission_no=s.admission_no, class_section_id=s.class_section_id
        )
        for s in exam_students(db, school_id, exam)
    }
    configs = {
        es.subject.id: dq.SubjectLimits(es.config.max_marks, es.config.pass_marks)
        for es in subjects
    }
    names = {es.subject.id: es.subject.name for es in subjects}
    return dq.validate_marks(sheet, column_map, roster, configs, names)


def _store_result(
    batch: ImportBatch,
    sheet: dq.ParsedSheet,
    column_map: dq.ColumnMap,
    result: dq.ValidationResult,
) -> None:
    batch.column_map = {**column_map.to_dict(), "headers": list(sheet.headers)}
    batch.issues = [i.to_dict() for i in result.issues]
    batch.preview = [r.to_dict() for r in result.rows]
    batch.status = ImportStatus.validated


def upload(
    db: Session, ctx: TenantContext, exam_id: int, filename: str, content: bytes
) -> ImportBatchDetail:
    exam = get_exam(db, ctx.school_id, exam_id)
    sheet = dq.parse_marks_file(content, filename)
    subjects = exam_subjects(db, ctx.school_id, exam.id)
    column_map = dq.suggest_column_map(
        sheet.headers,
        [
            dq.SubjectRef(id=es.subject.id, name=es.subject.name, code=es.subject.code)
            for es in subjects
        ],
    )

    original_name = Path(filename.replace("\\", "/")).name[:255] or "upload"
    batch = ImportBatch(
        school_id=ctx.school_id,
        exam_id=exam.id,
        filename=original_name,
        status=ImportStatus.uploaded,
        uploaded_by=ctx.user.id,
    )
    db.add(batch)
    db.flush()

    path = batch_file_path(batch)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)

    result = _run_validation(db, ctx.school_id, exam, sheet, column_map)
    _store_result(batch, sheet, column_map, result)
    log_action(
        db,
        school_id=ctx.school_id,
        user_id=ctx.user.id,
        actor="user",
        action="import.upload",
        entity_type="import_batch",
        entity_id=batch.id,
        detail={
            "exam_id": exam.id,
            "filename": original_name,
            "rows": len(result.rows),
            "errors": result.error_count,
            "warnings": result.warning_count,
        },
    )
    db.commit()
    logger.info(
        "Import batch %s uploaded for exam %s (%d rows, %d errors)",
        batch.id,
        exam.id,
        len(result.rows),
        result.error_count,
    )
    return build_detail(db, batch, exam)


def update_mapping(
    db: Session, ctx: TenantContext, batch_id: int, payload: ColumnMapUpdate
) -> ImportBatchDetail:
    batch = get_visible_batch(db, ctx, batch_id)
    if batch.status not in (ImportStatus.uploaded, ImportStatus.validated):
        raise ConflictError(f"Cannot change the mapping of a {batch.status.value} import")
    exam = get_exam(db, ctx.school_id, batch.exam_id)
    sheet = dq.parse_marks_file(_read_batch_file(batch), batch.filename)

    headers = set(sheet.headers)
    if payload.admission_column is not None and payload.admission_column not in headers:
        raise DomainValidationError(f'Unknown column "{payload.admission_column}"')
    allowed_subjects = {es.subject.id for es in exam_subjects(db, ctx.school_id, exam.id)}
    used: set[int] = set()
    for header, subject_id in payload.subjects.items():
        if header not in headers:
            raise DomainValidationError(f'Unknown column "{header}"')
        if subject_id is None:
            continue
        if header == payload.admission_column:
            raise DomainValidationError("The admission column cannot also be a subject column")
        if subject_id not in allowed_subjects:
            raise DomainValidationError(f"Subject {subject_id} is not configured for this exam")
        if subject_id in used:
            raise DomainValidationError("Each subject can be mapped to only one column")
        used.add(subject_id)

    column_map = dq.ColumnMap(
        admission_column=payload.admission_column,
        subjects={
            h: payload.subjects.get(h) for h in sheet.headers if h != payload.admission_column
        },
    )
    result = _run_validation(db, ctx.school_id, exam, sheet, column_map)
    _store_result(batch, sheet, column_map, result)
    log_action(
        db,
        school_id=ctx.school_id,
        user_id=ctx.user.id,
        actor="user",
        action="import.remap",
        entity_type="import_batch",
        entity_id=batch.id,
        detail={"errors": result.error_count, "warnings": result.warning_count},
    )
    db.commit()
    return build_detail(db, batch, exam)


# --- commit / reject -----------------------------------------------------------------------
def commit(db: Session, ctx: TenantContext, batch_id: int) -> CommitResult:
    batch = get_visible_batch(db, ctx, batch_id)
    if batch.status != ImportStatus.validated:
        raise ConflictError(
            f"Only validated imports can be committed (status: {batch.status.value})"
        )
    summary = dq.summarize_issues(batch.issues or [])
    if summary["errors"]:
        raise DomainValidationError(
            f"Fix the {summary['errors']} error(s) before committing", code="IMPORT_HAS_ERRORS"
        )
    rows: list[dict[str, Any]] = batch.preview or []
    if not rows:
        raise DomainValidationError("The import has no rows to commit", code="IMPORT_EMPTY")

    allowed_subjects = {es.subject.id for es in exam_subjects(db, ctx.school_id, batch.exam_id)}
    student_ids = {int(r["student_id"]) for r in rows if r.get("student_id") is not None}
    valid_students = set(
        db.scalars(
            select(Student.id).where(
                Student.school_id == ctx.school_id, Student.id.in_(student_ids)
            )
        )
    )
    if valid_students != student_ids:
        raise ConflictError("Some students changed since validation - re-validate the import")
    _check_teacher_write_scope(db, ctx, rows, allowed_subjects)

    existing = {
        (m.student_id, m.subject_id): m
        for m in db.scalars(
            select(Mark).where(
                Mark.school_id == ctx.school_id,
                Mark.exam_id == batch.exam_id,
                Mark.student_id.in_(student_ids),
            )
        )
    }
    inserted = updated = absent = skipped = 0
    try:
        for row in rows:
            student_id = row.get("student_id")
            if student_id is None:
                continue
            for cell in (row.get("marks") or {}).values():
                subject_id = int(cell["subject_id"])
                if subject_id not in allowed_subjects:
                    skipped += 1
                    continue
                is_absent = bool(cell.get("is_absent"))
                raw_value = cell.get("value")
                if not is_absent and raw_value is None:
                    skipped += 1  # blank cell: leave any existing mark untouched
                    continue
                value = None if is_absent else Decimal(str(raw_value))
                absent += int(is_absent)
                mark = existing.get((int(student_id), subject_id))
                if mark is None:
                    mark = Mark(
                        school_id=ctx.school_id,
                        exam_id=batch.exam_id,
                        student_id=int(student_id),
                        subject_id=subject_id,
                        marks_obtained=value,
                        is_absent=is_absent,
                    )
                    db.add(mark)
                    existing[(int(student_id), subject_id)] = mark
                    inserted += 1
                else:
                    mark.marks_obtained = value
                    mark.is_absent = is_absent
                    updated += 1
        batch.status = ImportStatus.committed
        counts = {"inserted": inserted, "updated": updated, "absent": absent, "skipped": skipped}
        log_action(
            db,
            school_id=ctx.school_id,
            user_id=ctx.user.id,
            actor="user",
            action="import.commit",
            entity_type="import_batch",
            entity_id=batch.id,
            detail={"exam_id": batch.exam_id, **counts},
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Commit of import batch %s failed", batch_id)
        raise
    logger.info("Import batch %s committed: %s", batch.id, counts)
    return CommitResult(batch_id=batch.id, **counts)


def reject(db: Session, ctx: TenantContext, batch_id: int) -> ImportBatchDetail:
    batch = get_visible_batch(db, ctx, batch_id)
    if batch.status == ImportStatus.committed:
        raise ConflictError("A committed import cannot be rejected")
    if batch.status != ImportStatus.rejected:
        batch.status = ImportStatus.rejected
        log_action(
            db,
            school_id=ctx.school_id,
            user_id=ctx.user.id,
            actor="user",
            action="import.reject",
            entity_type="import_batch",
            entity_id=batch.id,
            detail={"exam_id": batch.exam_id},
        )
        db.commit()
    return build_detail(db, batch, get_exam(db, ctx.school_id, batch.exam_id))


# --- read ----------------------------------------------------------------------------------
def _summary(batch: ImportBatch) -> IssueSummary:
    return IssueSummary(**dq.summarize_issues(batch.issues or []))


def build_detail(db: Session, batch: ImportBatch, exam: Exam) -> ImportBatchDetail:
    stored = batch.column_map or {}
    cmap = dq.ColumnMap.from_dict(stored)
    rows = batch.preview or []
    summary = _summary(batch)
    return ImportBatchDetail(
        id=batch.id,
        exam_id=batch.exam_id,
        exam_name=exam.name,
        filename=batch.filename,
        status=batch.status,
        row_count=len(rows),
        summary=summary,
        created_at=batch.created_at,
        column_map=ColumnMapOut(admission_column=cmap.admission_column, subjects=cmap.subjects),
        headers=[str(h) for h in stored.get("headers", [])],
        issues=[IssueOut.model_validate(i) for i in batch.issues or []],
        summary_text=dq.describe_issues(batch.issues or [], len(rows)),
        preview=[PreviewRow.model_validate(r) for r in rows[:PREVIEW_LIMIT]],
        can_commit=batch.status == ImportStatus.validated and summary.errors == 0 and bool(rows),
        exam_subjects=[
            ExamSubjectOut(
                id=es.subject.id,
                name=es.subject.name,
                code=es.subject.code,
                max_marks=es.config.max_marks,
                pass_marks=es.config.pass_marks,
            )
            for es in exam_subjects(db, batch.school_id, batch.exam_id)
        ],
        uploaded_by=batch.uploaded_by,
    )


def get_detail(db: Session, ctx: TenantContext, batch_id: int) -> ImportBatchDetail:
    batch = get_visible_batch(db, ctx, batch_id)
    return build_detail(db, batch, get_exam(db, ctx.school_id, batch.exam_id))


def list_batches(
    db: Session, ctx: TenantContext, exam_id: int | None = None
) -> list[ImportBatchListItem]:
    stmt = (
        select(ImportBatch, Exam.name)
        .join(Exam, Exam.id == ImportBatch.exam_id)
        .where(ImportBatch.school_id == ctx.school_id)
        .order_by(ImportBatch.created_at.desc(), ImportBatch.id.desc())
        .limit(LIST_LIMIT)
    )
    if exam_id is not None:
        stmt = stmt.where(ImportBatch.exam_id == exam_id)
    if is_restricted_teacher(ctx):
        stmt = stmt.where(ImportBatch.uploaded_by == ctx.user.id)
    return [
        ImportBatchListItem(
            id=batch.id,
            exam_id=batch.exam_id,
            exam_name=exam_name,
            filename=batch.filename,
            status=batch.status,
            row_count=len(batch.preview or []),
            summary=_summary(batch),
            created_at=batch.created_at,
        )
        for batch, exam_name in db.execute(stmt).all()
    ]


def build_template(db: Session, ctx: TenantContext, exam_id: int) -> tuple[str, str]:
    """CSV template for an exam -> (filename, csv text)."""
    exam = get_exam(db, ctx.school_id, exam_id)
    subjects = exam_subjects(db, ctx.school_id, exam.id)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["admission_no", *(es.subject.name for es in subjects)])
    for student in exam_students(db, ctx.school_id, exam):
        writer.writerow([student.admission_no, *([""] * len(subjects))])
    slug = re.sub(r"[^A-Za-z0-9]+", "_", exam.name).strip("_").lower() or "exam"
    return f"marks_template_{slug}.csv", buffer.getvalue()
