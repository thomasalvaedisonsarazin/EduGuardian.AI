"""Response schemas for /api/v1/analytics.

They mirror the dataclasses in ``app.analytics`` (validated with ``from_attributes``).
Decimal fields serialise as JSON strings (e.g. ``"72.50"``), matching ``to_dict()``.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ExamRefOut(_Out):
    id: int
    name: str
    sequence: int
    held_on: date | None
    academic_year_id: int
    academic_year_label: str


class ExamListItemOut(_Out):
    exam: ExamRefOut
    mark_count: int
    has_marks: bool


class SubjectConfigOut(_Out):
    subject_id: int
    name: str
    max_marks: Decimal
    pass_marks: Decimal


class StudentInfoOut(_Out):
    student_id: int
    pseudo_id: str
    full_name: str
    class_section_id: int
    class_label: str


class SubjectResultOut(_Out):
    subject_id: int
    subject_name: str
    marks: Decimal | None
    max_marks: Decimal
    pass_marks: Decimal
    is_absent: bool
    is_missing: bool
    passed: bool
    percentage: Decimal


class StudentResultOut(_Out):
    student_id: int
    pseudo_id: str
    full_name: str
    class_section_id: int
    class_label: str
    subjects: list[SubjectResultOut]
    total: Decimal
    max_total: Decimal
    percentage: Decimal
    passed: bool
    appeared: bool
    failed_subjects: list[int]
    rank_in_section: int
    section_size: int


class DistributionBandOut(_Out):
    label: str
    lower: Decimal
    upper: Decimal
    count: int


class ClassSummaryOut(_Out):
    class_section_id: int | None
    class_label: str
    student_count: int
    appeared_count: int
    pass_count: int
    fail_count: int
    pass_percentage: Decimal | None
    mean_percentage: Decimal | None
    median_percentage: Decimal | None
    highest_percentage: Decimal | None
    lowest_percentage: Decimal | None
    distribution: list[DistributionBandOut]


class SubjectStatsOut(_Out):
    student_count: int
    appeared_count: int
    absent_count: int
    missing_count: int
    pass_count: int
    pass_percentage: Decimal | None
    mean_marks: Decimal | None
    mean_percentage: Decimal | None
    highest_marks: Decimal | None
    lowest_marks: Decimal | None


class SectionSubjectStatsOut(_Out):
    class_section_id: int
    class_label: str
    stats: SubjectStatsOut


class SubjectSummaryOut(_Out):
    subject_id: int
    subject_name: str
    max_marks: Decimal
    pass_marks: Decimal
    overall: SubjectStatsOut
    sections: list[SectionSubjectStatsOut]
    weakest_sections: list[int]
    mean_percentage_change: Decimal | None


class SubjectChangeOut(_Out):
    subject_id: int
    subject_name: str
    previous_percentage: Decimal
    current_percentage: Decimal
    delta: Decimal


class StudentChangeOut(_Out):
    student_id: int
    previous_percentage: Decimal
    current_percentage: Decimal
    delta: Decimal
    subjects: list[SubjectChangeOut]


class RiskReasonOut(_Out):
    code: Literal["FAILED_SUBJECTS", "SHARP_DROP", "LOW_OVERALL"]
    detail: str
    evidence: dict[str, Any]


class AtRiskStudentOut(_Out):
    student_id: int
    pseudo_id: str
    full_name: str
    class_section_id: int
    class_label: str
    percentage: Decimal
    failed_subject_count: int
    delta: Decimal | None
    severity: Literal["high", "medium"]
    reasons: list[RiskReasonOut]


# ---------------------------------------------------------------------------
# Endpoint responses
# ---------------------------------------------------------------------------


class ExamSummaryResponse(BaseModel):
    exam: ExamRefOut
    previous_exam: ExamRefOut | None
    comparison_exam_id: int | None
    class_section_ids: list[int] | None
    subjects: list[SubjectConfigOut]
    school_summary: ClassSummaryOut
    class_summaries: list[ClassSummaryOut]
    subject_summaries: list[SubjectSummaryOut]
    at_risk_count: int
    at_risk_high_count: int
    at_risk: list[AtRiskStudentOut]


class ClassAnalyticsResponse(BaseModel):
    exam: ExamRefOut
    previous_exam: ExamRefOut | None
    class_section_id: int
    class_label: str
    summary: ClassSummaryOut
    subjects: list[SubjectConfigOut]
    subject_summaries: list[SubjectSummaryOut]
    results: list[StudentResultOut]
    changes: list[StudentChangeOut]
    at_risk: list[AtRiskStudentOut]


class SubjectStudentRow(BaseModel):
    student_id: int
    pseudo_id: str
    full_name: str
    class_section_id: int
    class_label: str
    marks: Decimal | None
    is_absent: bool
    is_missing: bool
    passed: bool
    percentage: Decimal
    delta: Decimal | None  # subject percentage-point change vs previous exam


class SubjectAnalyticsResponse(BaseModel):
    exam: ExamRefOut
    previous_exam: ExamRefOut | None
    summary: SubjectSummaryOut
    students: list[SubjectStudentRow]


class AtRiskResponse(BaseModel):
    exam: ExamRefOut
    previous_exam: ExamRefOut | None
    count: int
    high_count: int
    students: list[AtRiskStudentOut]


class StudentTrendPointOut(_Out):
    exam: ExamRefOut
    result: StudentResultOut
    comparison_exam_id: int | None
    change: StudentChangeOut | None
    at_risk: AtRiskStudentOut | None
    section_pass_percentage: Decimal | None
    section_mean_percentage: Decimal | None


class StudentTrendResponse(_Out):
    student: StudentInfoOut
    points: list[StudentTrendPointOut]


class SupportStudentOut(_Out):
    student_id: int
    pseudo_id: str
    full_name: str
    marks: Decimal | None
    is_absent: bool
    is_missing: bool


class TeacherAssignmentInsightOut(_Out):
    class_section_id: int
    class_label: str
    subject_id: int
    subject_name: str
    is_class_teacher: bool
    in_exam: bool
    stats: SubjectStatsOut | None
    mean_change_points: Decimal | None
    at_risk_count: int
    students_needing_support: list[SupportStudentOut]
    notes: list[str]


class TeacherViewResponse(_Out):
    teacher_id: int
    teacher_name: str
    exam: ExamRefOut
    previous_exam: ExamRefOut | None
    assignments: list[TeacherAssignmentInsightOut]
    combined: SubjectStatsOut | None
    notes: list[str]


class ExamTrendPointOut(_Out):
    exam: ExamRefOut
    student_count: int
    pass_percentage: Decimal | None
    mean_percentage: Decimal | None
    median_percentage: Decimal | None


class DashboardOverviewResponse(_Out):
    student_count: int
    class_section_count: int
    exams_with_marks: int
    latest_exam: ExamRefOut | None
    previous_exam: ExamRefOut | None
    summary: ClassSummaryOut | None
    at_risk_count: int
    at_risk_high_count: int
    at_risk_preview: list[AtRiskStudentOut]
    subjects: list[SubjectSummaryOut]
    trend: list[ExamTrendPointOut]
