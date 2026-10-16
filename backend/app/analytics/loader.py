"""Database loading for the analytics engine (tenant-scoped, read-only).

Converts ORM rows into the plain dataclasses consumed by ``app.analytics.calculations``.

Population rule: an exam's dataset contains every student of the class sections that have at
least one mark recorded for that exam (optionally narrowed by ``class_section_ids``). Students
in those sections with no marks are included - their papers count as missing (= failed).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.calculations import MarkRecord, Serializable, StudentInfo, SubjectConfig
from app.exceptions import NotFoundError
from app.models import (
    AcademicYear,
    ClassSection,
    Exam,
    ExamSubjectConfig,
    Mark,
    Student,
    Subject,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ExamDataset",
    "ExamRef",
    "class_label",
    "exams_with_marks",
    "get_class_section",
    "get_exam",
    "load_exam_dataset",
    "previous_exam_id",
]


@dataclass(frozen=True)
class ExamRef(Serializable):
    id: int
    name: str
    sequence: int
    held_on: date | None
    academic_year_id: int
    academic_year_label: str


@dataclass(frozen=True)
class ExamDataset(Serializable):
    exam: ExamRef
    students: list[StudentInfo]
    configs: list[SubjectConfig]
    marks: list[MarkRecord]

    @property
    def exam_id(self) -> int:
        return self.exam.id


def class_label(section: ClassSection) -> str:
    """Human label for a section, e.g. ``"8-A"``."""
    return f"{section.grade}-{section.section}"


def _exam_ref(exam: Exam, year_label: str) -> ExamRef:
    return ExamRef(
        id=exam.id,
        name=exam.name,
        sequence=exam.sequence,
        held_on=exam.held_on,
        academic_year_id=exam.academic_year_id,
        academic_year_label=year_label,
    )


def get_exam(db: Session, school_id: int, exam_id: int) -> ExamRef:
    """Exam reference scoped to the tenant; raises ``NotFoundError`` for foreign/unknown ids."""
    row = db.execute(
        select(Exam, AcademicYear.label)
        .join(AcademicYear, AcademicYear.id == Exam.academic_year_id)
        .where(Exam.id == exam_id, Exam.school_id == school_id)
    ).first()
    if row is None:
        raise NotFoundError("Exam")
    return _exam_ref(row[0], row[1])


def get_class_section(db: Session, school_id: int, class_section_id: int) -> ClassSection:
    section = db.scalar(
        select(ClassSection).where(
            ClassSection.id == class_section_id, ClassSection.school_id == school_id
        )
    )
    if section is None:
        raise NotFoundError("Class section")
    return section


def _validate_sections(db: Session, school_id: int, class_section_ids: Sequence[int]) -> None:
    wanted = set(class_section_ids)
    found = set(
        db.scalars(
            select(ClassSection.id).where(
                ClassSection.id.in_(wanted), ClassSection.school_id == school_id
            )
        )
    )
    if wanted - found:
        raise NotFoundError("Class section")


def load_exam_dataset(
    db: Session,
    school_id: int,
    exam_id: int,
    class_section_ids: list[int] | None = None,
) -> ExamDataset:
    """Load students, subject configs and marks for one exam (see module docstring)."""
    exam = get_exam(db, school_id, exam_id)
    if class_section_ids:
        _validate_sections(db, school_id, class_section_ids)

    config_rows = db.execute(
        select(ExamSubjectConfig, Subject.name)
        .join(Subject, Subject.id == ExamSubjectConfig.subject_id)
        .where(ExamSubjectConfig.exam_id == exam_id, ExamSubjectConfig.school_id == school_id)
        .order_by(Subject.name, Subject.id)
    ).all()
    configs = [
        SubjectConfig(
            subject_id=cfg.subject_id,
            name=name,
            max_marks=cfg.max_marks,
            pass_marks=cfg.pass_marks,
        )
        for cfg, name in config_rows
    ]

    sections_with_marks = (
        select(Student.class_section_id)
        .join(Mark, Mark.student_id == Student.id)
        .where(Mark.exam_id == exam_id, Mark.school_id == school_id)
        .distinct()
    )
    student_query = (
        select(Student, ClassSection)
        .join(ClassSection, ClassSection.id == Student.class_section_id)
        .where(Student.school_id == school_id, Student.class_section_id.in_(sections_with_marks))
        .order_by(ClassSection.grade, ClassSection.section, Student.pseudo_id, Student.id)
    )
    if class_section_ids:
        student_query = student_query.where(Student.class_section_id.in_(class_section_ids))
    students = [
        StudentInfo(
            student_id=student.id,
            pseudo_id=student.pseudo_id,
            full_name=student.full_name,
            class_section_id=section.id,
            class_label=class_label(section),
        )
        for student, section in db.execute(student_query).all()
    ]

    marks: list[MarkRecord] = []
    if students:
        mark_rows = db.scalars(
            select(Mark).where(
                Mark.exam_id == exam_id,
                Mark.school_id == school_id,
                Mark.student_id.in_([s.student_id for s in students]),
            )
        ).all()
        marks = [
            MarkRecord(
                student_id=m.student_id,
                subject_id=m.subject_id,
                marks=m.marks_obtained,
                is_absent=m.is_absent,
            )
            for m in mark_rows
        ]

    logger.debug(
        "Loaded exam dataset school=%s exam=%s students=%d subjects=%d marks=%d",
        school_id,
        exam_id,
        len(students),
        len(configs),
        len(marks),
    )
    return ExamDataset(exam=exam, students=students, configs=configs, marks=marks)


def previous_exam_id(db: Session, school_id: int, exam_id: int) -> int | None:
    """Comparison exam: same academic year, highest ``sequence`` below this exam's, with marks.

    Exams that have no marks recorded yet are skipped (nothing to compare against).
    """
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id))
    if exam is None:
        raise NotFoundError("Exam")
    has_marks = select(Mark.exam_id).where(Mark.school_id == school_id).distinct()
    return db.scalar(
        select(Exam.id)
        .where(
            Exam.school_id == school_id,
            Exam.academic_year_id == exam.academic_year_id,
            Exam.sequence < exam.sequence,
            Exam.id.in_(has_marks),
        )
        .order_by(Exam.sequence.desc(), Exam.id.desc())
        .limit(1)
    )


def exams_with_marks(db: Session, school_id: int) -> list[tuple[ExamRef, int]]:
    """All exams of the school with their mark count, oldest first (year label, sequence)."""
    mark_counts = (
        select(Mark.exam_id, func.count(Mark.id).label("n"))
        .where(Mark.school_id == school_id)
        .group_by(Mark.exam_id)
        .subquery()
    )
    rows = db.execute(
        select(Exam, AcademicYear.label, func.coalesce(mark_counts.c.n, 0))
        .join(AcademicYear, AcademicYear.id == Exam.academic_year_id)
        .outerjoin(mark_counts, mark_counts.c.exam_id == Exam.id)
        .where(Exam.school_id == school_id)
        .order_by(AcademicYear.label, Exam.sequence, Exam.id)
    ).all()
    return [(_exam_ref(exam, label), int(count)) for exam, label, count in rows]
