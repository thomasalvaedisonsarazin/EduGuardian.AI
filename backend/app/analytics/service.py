"""Analytics facade: the functions other modules (Orchestrator, Intervention, Reporting) call.

Every function is tenant-scoped by ``school_id`` and raises ``NotFoundError`` for ids that do
not belong to the school. Results are dataclasses with ``to_dict()`` (JSON-safe, Decimals as
strings) so they can be stored in ``AgentStep.output_summary`` or rendered into reports.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.calculations import (
    AtRiskStudent,
    ClassSummary,
    Serializable,
    StudentChange,
    StudentInfo,
    StudentResult,
    SubjectConfig,
    SubjectResult,
    SubjectStats,
    SubjectSummary,
    at_risk_students,
    class_summary,
    compare_exams,
    quantize,
    student_results,
    subject_stats,
    subject_summary,
)
from app.analytics.loader import (
    ExamDataset,
    ExamRef,
    class_label,
    exams_with_marks,
    get_exam,
    load_exam_dataset,
    previous_exam_id,
)
from app.exceptions import NotFoundError
from app.models import ClassSection, Mark, Student, Subject, Teacher, TeachingAssignment

logger = logging.getLogger(__name__)

__all__ = [
    "DashboardOverview",
    "ExamListItem",
    "ExamOverview",
    "ExamTrendPoint",
    "StudentTrend",
    "StudentTrendPoint",
    "SupportStudent",
    "TeacherAssignmentInsight",
    "TeacherView",
    "dashboard_overview",
    "exam_overview",
    "list_exams",
    "student_trend",
    "teacher_view",
]

DASHBOARD_TREND_EXAMS = 8
DASHBOARD_AT_RISK_PREVIEW = 5


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExamOverview(Serializable):
    exam: ExamRef
    previous_exam: ExamRef | None
    comparison_exam_id: int | None
    class_section_ids: list[int] | None  # the filter applied (None = whole school)
    subjects: list[SubjectConfig]
    school_summary: ClassSummary
    class_summaries: list[ClassSummary]
    subject_summaries: list[SubjectSummary]
    at_risk: list[AtRiskStudent]
    results: list[StudentResult]
    changes: list[StudentChange]

    def change_for(self, student_id: int) -> StudentChange | None:
        return next((c for c in self.changes if c.student_id == student_id), None)


@dataclass(frozen=True)
class SupportStudent(Serializable):
    student_id: int
    pseudo_id: str
    full_name: str
    marks: Decimal | None
    is_absent: bool
    is_missing: bool


@dataclass(frozen=True)
class TeacherAssignmentInsight(Serializable):
    class_section_id: int
    class_label: str
    subject_id: int
    subject_name: str
    is_class_teacher: bool
    in_exam: bool  # False when the subject is not configured for this exam
    stats: SubjectStats | None
    mean_change_points: Decimal | None  # average per-student subject change vs previous exam
    at_risk_count: int  # at-risk students in this section (any reason)
    students_needing_support: list[SupportStudent]
    notes: list[str]


@dataclass(frozen=True)
class TeacherView(Serializable):
    """Coaching view of a teacher's classes. Deliberately contains no teacher score or rank."""

    teacher_id: int
    teacher_name: str
    exam: ExamRef
    previous_exam: ExamRef | None
    assignments: list[TeacherAssignmentInsight]
    combined: SubjectStats | None
    notes: list[str]


@dataclass(frozen=True)
class StudentTrendPoint(Serializable):
    exam: ExamRef
    result: StudentResult
    comparison_exam_id: int | None
    change: StudentChange | None
    at_risk: AtRiskStudent | None
    section_pass_percentage: Decimal | None
    section_mean_percentage: Decimal | None


@dataclass(frozen=True)
class StudentTrend(Serializable):
    student: StudentInfo
    points: list[StudentTrendPoint]


@dataclass(frozen=True)
class ExamTrendPoint(Serializable):
    exam: ExamRef
    student_count: int
    pass_percentage: Decimal | None
    mean_percentage: Decimal | None
    median_percentage: Decimal | None


@dataclass(frozen=True)
class DashboardOverview(Serializable):
    student_count: int
    class_section_count: int
    exams_with_marks: int
    latest_exam: ExamRef | None
    previous_exam: ExamRef | None
    summary: ClassSummary | None
    at_risk_count: int
    at_risk_high_count: int
    at_risk_preview: list[AtRiskStudent]
    subjects: list[SubjectSummary]
    trend: list[ExamTrendPoint] = field(default_factory=list)


@dataclass(frozen=True)
class ExamListItem(Serializable):
    exam: ExamRef
    mark_count: int
    has_marks: bool


# ---------------------------------------------------------------------------
# Exam overview
# ---------------------------------------------------------------------------


def _analyse(dataset: ExamDataset) -> list[StudentResult]:
    return student_results(dataset.students, dataset.configs, dataset.marks)


def _class_summaries(results: Sequence[StudentResult]) -> list[ClassSummary]:
    groups: dict[int, list[StudentResult]] = {}
    for r in results:
        groups.setdefault(r.class_section_id, []).append(r)
    return [class_summary(rows, sid, rows[0].class_label) for sid, rows in groups.items()]


def exam_overview(
    db: Session,
    school_id: int,
    exam_id: int,
    class_section_ids: list[int] | None = None,
) -> ExamOverview:
    """Full deterministic analysis of one exam (optionally restricted to some sections).

    Includes school/group summary, per-section summaries, per-subject summaries (with mean
    change vs the comparison exam), per-student results, exam-over-exam changes and the
    at-risk list. Raises ``NotFoundError`` for a foreign exam or class section.
    """
    dataset = load_exam_dataset(db, school_id, exam_id, class_section_ids)
    results = _analyse(dataset)

    prev_id = previous_exam_id(db, school_id, exam_id)
    previous_exam: ExamRef | None = None
    changes: list[StudentChange] = []
    previous_subjects: list[SubjectSummary] | None = None
    if prev_id is not None:
        prev_dataset = load_exam_dataset(db, school_id, prev_id, class_section_ids)
        previous_exam = prev_dataset.exam
        prev_results = _analyse(prev_dataset)
        changes = compare_exams(prev_results, results)
        previous_subjects = subject_summary(prev_results, prev_dataset.configs)

    overview = ExamOverview(
        exam=dataset.exam,
        previous_exam=previous_exam,
        comparison_exam_id=prev_id,
        class_section_ids=sorted(class_section_ids) if class_section_ids else None,
        subjects=dataset.configs,
        school_summary=class_summary(
            results, None, "Selected classes" if class_section_ids else "All classes"
        ),
        class_summaries=_class_summaries(results),
        subject_summaries=subject_summary(results, dataset.configs, previous_subjects),
        at_risk=at_risk_students(results, changes),
        results=results,
        changes=changes,
    )
    logger.info(
        "Exam overview school=%s exam=%s students=%d at_risk=%d compared_with=%s",
        school_id,
        exam_id,
        len(results),
        len(overview.at_risk),
        prev_id,
    )
    return overview


# ---------------------------------------------------------------------------
# Teacher coaching view
# ---------------------------------------------------------------------------


def _assignment_notes(
    label: str,
    subject: str,
    stats: SubjectStats,
    change: Decimal | None,
    previous_exam: ExamRef | None,
) -> list[str]:
    where = f"{subject} in {label}"
    if stats.appeared_count == 0:
        return [f"No marks recorded yet for {where}."]
    notes: list[str] = []
    below = stats.student_count - stats.pass_count - stats.absent_count - stats.missing_count
    if below > 0:
        noun = "student is" if below == 1 else "students are"
        notes.append(
            f"{below} {noun} below the pass mark in {where} - consider targeted revision "
            "or small-group support."
        )
    if stats.absent_count:
        notes.append(f"{stats.absent_count} absent for {where} - plan a make-up assessment.")
    if stats.pass_count == stats.student_count:
        notes.append(f"Everyone passed {where} - keep stretching the strongest learners.")
    if change is not None and previous_exam is not None:
        if change > 0:
            notes.append(
                f"Average {subject} score in {label} improved by {change} points since "
                f"{previous_exam.name} - worth noting what worked."
            )
        elif change < 0:
            notes.append(
                f"Average {subject} score in {label} fell by {abs(change)} points since "
                f"{previous_exam.name} - review which topics were assessed."
            )
    return notes


def teacher_view(db: Session, school_id: int, teacher_id: int, exam_id: int) -> TeacherView:
    """Per class+subject and combined results for a teacher's assignments in one exam."""
    teacher = db.scalar(
        select(Teacher).where(Teacher.id == teacher_id, Teacher.school_id == school_id)
    )
    if teacher is None:
        raise NotFoundError("Teacher")
    exam = get_exam(db, school_id, exam_id)

    rows = db.execute(
        select(TeachingAssignment, ClassSection, Subject)
        .join(ClassSection, ClassSection.id == TeachingAssignment.class_section_id)
        .join(Subject, Subject.id == TeachingAssignment.subject_id)
        .where(
            TeachingAssignment.teacher_id == teacher_id,
            TeachingAssignment.school_id == school_id,
            ClassSection.academic_year_id == exam.academic_year_id,
        )
        .order_by(ClassSection.grade, ClassSection.section, Subject.name)
    ).all()

    overview: ExamOverview | None = None
    if rows:
        section_ids = sorted({section.id for _, section, _ in rows})
        overview = exam_overview(db, school_id, exam_id, section_ids)

    configured = {c.subject_id for c in overview.subjects} if overview else set()
    insights: list[TeacherAssignmentInsight] = []
    all_entries: list[SubjectResult] = []
    for assignment, section, subject in rows:
        label = class_label(section)
        if overview is None or subject.id not in configured:
            insights.append(
                TeacherAssignmentInsight(
                    class_section_id=section.id,
                    class_label=label,
                    subject_id=subject.id,
                    subject_name=subject.name,
                    is_class_teacher=assignment.is_class_teacher,
                    in_exam=False,
                    stats=None,
                    mean_change_points=None,
                    at_risk_count=0,
                    students_needing_support=[],
                    notes=[f"{subject.name} is not part of {exam.name}."],
                )
            )
            continue
        section_results = [r for r in overview.results if r.class_section_id == section.id]
        entries: list[tuple[StudentResult, SubjectResult]] = []
        for r in section_results:
            entry = r.subject(subject.id)
            if entry is not None:
                entries.append((r, entry))
        stats = subject_stats([e for _, e in entries])
        all_entries.extend(e for _, e in entries)

        deltas = [
            sc.delta
            for r, _ in entries
            if (change := overview.change_for(r.student_id)) is not None
            for sc in change.subjects
            if sc.subject_id == subject.id
        ]
        mean_change = quantize(sum(deltas, Decimal(0)) / len(deltas)) if deltas else None
        insights.append(
            TeacherAssignmentInsight(
                class_section_id=section.id,
                class_label=label,
                subject_id=subject.id,
                subject_name=subject.name,
                is_class_teacher=assignment.is_class_teacher,
                in_exam=True,
                stats=stats,
                mean_change_points=mean_change,
                at_risk_count=sum(1 for a in overview.at_risk if a.class_section_id == section.id),
                students_needing_support=[
                    SupportStudent(
                        student_id=r.student_id,
                        pseudo_id=r.pseudo_id,
                        full_name=r.full_name,
                        marks=e.marks,
                        is_absent=e.is_absent,
                        is_missing=e.is_missing,
                    )
                    for r, e in entries
                    if not e.passed
                ],
                notes=_assignment_notes(
                    label,
                    subject.name,
                    stats,
                    mean_change,
                    overview.previous_exam,
                ),
            )
        )

    combined = subject_stats(all_entries) if all_entries else None
    notes: list[str] = []
    if not rows:
        notes.append("No teaching assignments in this exam's academic year.")
    elif combined is not None:
        support = sum(len(i.students_needing_support) for i in insights)
        notes.append(
            f"Across {len(insights)} class-subject assignments, {combined.pass_count} of "
            f"{combined.student_count} papers met the pass mark."
        )
        if support:
            notes.append(
                f"{support} student-subject results need follow-up; start with the classes "
                "that have the most students below the pass mark."
            )
    return TeacherView(
        teacher_id=teacher.id,
        teacher_name=teacher.full_name,
        exam=exam,
        previous_exam=overview.previous_exam if overview else None,
        assignments=insights,
        combined=combined,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Student trend
# ---------------------------------------------------------------------------


def student_trend(db: Session, school_id: int, student_id: int) -> StudentTrend:
    """A student's result in every exam with their marks, oldest first, with changes/risk."""
    row = db.execute(
        select(Student, ClassSection)
        .join(ClassSection, ClassSection.id == Student.class_section_id)
        .where(Student.id == student_id, Student.school_id == school_id)
    ).first()
    if row is None:
        raise NotFoundError("Student")
    student, section = row
    info = StudentInfo(
        student_id=student.id,
        pseudo_id=student.pseudo_id,
        full_name=student.full_name,
        class_section_id=section.id,
        class_label=class_label(section),
    )
    exam_ids_with_marks = set(
        db.scalars(
            select(Mark.exam_id)
            .where(Mark.student_id == student_id, Mark.school_id == school_id)
            .distinct()
        )
    )
    exams = [ref for ref, _ in exams_with_marks(db, school_id) if ref.id in exam_ids_with_marks]

    section_results: dict[int, list[StudentResult]] = {}
    points: list[StudentTrendPoint] = []
    for exam in exams:
        dataset = load_exam_dataset(db, school_id, exam.id, [section.id])
        results = _analyse(dataset)
        section_results[exam.id] = results
        mine = next((r for r in results if r.student_id == student_id), None)
        if mine is None:
            continue
        prev_id = previous_exam_id(db, school_id, exam.id)
        change: StudentChange | None = None
        if prev_id is not None and prev_id in section_results:
            found = compare_exams(section_results[prev_id], [mine])
            change = found[0] if found else None
        risk = at_risk_students([mine], [change] if change else [])
        summary = class_summary(results, section.id, info.class_label)
        points.append(
            StudentTrendPoint(
                exam=exam,
                result=mine,
                comparison_exam_id=prev_id,
                change=change,
                at_risk=risk[0] if risk else None,
                section_pass_percentage=summary.pass_percentage,
                section_mean_percentage=summary.mean_percentage,
            )
        )
    return StudentTrend(student=info, points=points)


# ---------------------------------------------------------------------------
# Dashboard + exam list
# ---------------------------------------------------------------------------


def list_exams(db: Session, school_id: int) -> list[ExamListItem]:
    """All exams (oldest first) with how many marks are recorded."""
    return [
        ExamListItem(exam=ref, mark_count=count, has_marks=count > 0)
        for ref, count in exams_with_marks(db, school_id)
    ]


def dashboard_overview(db: Session, school_id: int) -> DashboardOverview:
    """Headline numbers for the latest exam with marks plus a pass/mean trend across exams."""
    student_count = (
        db.scalar(select(func.count(Student.id)).where(Student.school_id == school_id)) or 0
    )
    section_count = (
        db.scalar(select(func.count(ClassSection.id)).where(ClassSection.school_id == school_id))
        or 0
    )
    with_marks = [ref for ref, count in exams_with_marks(db, school_id) if count > 0]
    if not with_marks:
        return DashboardOverview(
            student_count=student_count,
            class_section_count=section_count,
            exams_with_marks=0,
            latest_exam=None,
            previous_exam=None,
            summary=None,
            at_risk_count=0,
            at_risk_high_count=0,
            at_risk_preview=[],
            subjects=[],
            trend=[],
        )

    latest = with_marks[-1]
    overview = exam_overview(db, school_id, latest.id)
    trend: list[ExamTrendPoint] = []
    for ref in with_marks[-DASHBOARD_TREND_EXAMS:]:
        if ref.id == latest.id:
            summary = overview.school_summary
        else:
            summary = class_summary(_analyse(load_exam_dataset(db, school_id, ref.id)))
        trend.append(
            ExamTrendPoint(
                exam=ref,
                student_count=summary.student_count,
                pass_percentage=summary.pass_percentage,
                mean_percentage=summary.mean_percentage,
                median_percentage=summary.median_percentage,
            )
        )
    return DashboardOverview(
        student_count=student_count,
        class_section_count=section_count,
        exams_with_marks=len(with_marks),
        latest_exam=overview.exam,
        previous_exam=overview.previous_exam,
        summary=overview.school_summary,
        at_risk_count=len(overview.at_risk),
        at_risk_high_count=sum(1 for a in overview.at_risk if a.severity == "high"),
        at_risk_preview=overview.at_risk[:DASHBOARD_AT_RISK_PREVIEW],
        subjects=overview.subject_summaries,
        trend=trend,
    )
