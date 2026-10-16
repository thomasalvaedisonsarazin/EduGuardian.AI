"""Deterministic performance-analysis calculations (pure functions, no database access).

Everything here operates on plain frozen dataclasses so results can be verified against
hand-computed fixtures and stored as JSON (every result type exposes ``to_dict()``, which
renders ``Decimal`` values as strings).

Rules
-----
Subject outcome
    * A subject counts toward a student's result only if it is configured for the exam
      (``SubjectConfig``). Marks for unconfigured subjects are ignored.
    * A mark is *absent* when ``is_absent`` is true, *missing* when there is no record or the
      record has ``marks is None``. Absent and missing marks both mean the subject is **failed**
      and contribute **0** toward the total.
    * Otherwise the subject is passed when ``marks >= pass_marks``.
    * Subject percentage = marks / max_marks x 100 (0 for absent/missing).

Student result
    * total = sum of obtained marks over configured subjects.
    * max_total = sum of ``max_marks`` over all configured subjects.
    * percentage = total / max_total x 100, rounded to 2 dp (``Decimal`` ROUND_HALF_UP);
      0 when ``max_total`` is 0.
    * passed (overall) = the exam has at least one configured subject AND every configured
      subject was passed.
    * appeared = at least one configured subject has a non-absent, non-null mark.
    * rank_in_section: competition ranking ("1, 2, 2, 4") by percentage descending among the
      students of the same class section in the input.

Class / group summary (``class_summary``)
    * student_count = number of students in the input; pass_count/pass_percentage are computed
      over **all** students (absent = fail).
    * mean, median, highest, lowest and the distribution bands are computed over students who
      **appeared** (a student absent from every paper would otherwise skew them to 0).
    * Bands: [0, 35), [35, 50), [50, 75), [75, 90), [90, 100] - upper bounds exclusive except
      the last band, which includes 100.

Subject summary (``subject_summary``)
    * Per subject and per section: student count, appeared, absent and missing counts, pass
      count / %, mean / highest / lowest raw marks (over students with a mark) and mean
      subject percentage. ``weakest_sections`` lists the section(s) with the lowest pass %.
    * When previous-exam summaries are supplied, ``mean_percentage_change`` is the change in
      the subject's mean percentage (percentage points).

Exam comparison (``compare_exams``)
    * For every student present in both result lists: delta = current% - previous% (points)
      and the same per subject configured in both exams.

At-risk rule (INITIAL.md, Module 4) - a student is at risk when ANY of:
    * FAILED_SUBJECTS: failed >= 1 configured subject (absent/missing counts as failed);
    * SHARP_DROP: overall percentage dropped >= 15 percentage points vs the previous exam;
    * LOW_OVERALL: overall percentage < 40%.
    Severity is ``high`` with >= 2 reasons or >= 3 failed subjects, otherwise ``medium``.
"""

from __future__ import annotations

import dataclasses
import enum
import statistics
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

__all__ = [
    "AT_RISK_DROP_POINTS",
    "DISTRIBUTION_BANDS",
    "LOW_OVERALL_THRESHOLD",
    "AtRiskStudent",
    "Serializable",
    "ClassSummary",
    "DistributionBand",
    "MarkRecord",
    "RiskReason",
    "SectionSubjectStats",
    "StudentChange",
    "StudentInfo",
    "StudentResult",
    "SubjectChange",
    "SubjectConfig",
    "SubjectResult",
    "SubjectStats",
    "SubjectSummary",
    "at_risk_students",
    "class_summary",
    "compare_exams",
    "quantize",
    "student_results",
    "subject_stats",
    "subject_summary",
    "to_jsonable",
]

TWO_PLACES = Decimal("0.01")
HUNDRED = Decimal("100")
ZERO = Decimal("0")

#: At-risk thresholds (INITIAL.md).
AT_RISK_DROP_POINTS = Decimal("15")
LOW_OVERALL_THRESHOLD = Decimal("40")
HIGH_SEVERITY_FAILED_SUBJECTS = 3

#: (label, lower inclusive, upper exclusive - except the last band which includes 100)
DISTRIBUTION_BANDS: tuple[tuple[str, Decimal, Decimal], ...] = (
    ("0-35", Decimal("0"), Decimal("35")),
    ("35-50", Decimal("35"), Decimal("50")),
    ("50-75", Decimal("50"), Decimal("75")),
    ("75-90", Decimal("75"), Decimal("90")),
    ("90-100", Decimal("90"), Decimal("100")),
)

RiskCode = Literal["FAILED_SUBJECTS", "SHARP_DROP", "LOW_OVERALL"]
Severity = Literal["high", "medium"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def quantize(value: Decimal) -> Decimal:
    """Round to 2 dp with ROUND_HALF_UP (the single rounding rule used everywhere)."""
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _pct(part: Decimal, whole: Decimal) -> Decimal:
    if whole == 0:
        return quantize(ZERO)
    return quantize(part / whole * HUNDRED)


def _count_pct(part: int, whole: int) -> Decimal | None:
    if whole == 0:
        return None
    return quantize(Decimal(part) / Decimal(whole) * HUNDRED)


def _mean(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    return quantize(sum(values, ZERO) / Decimal(len(values)))


def _median(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None
    return quantize(Decimal(statistics.median(values)))


def to_jsonable(value: Any) -> Any:
    """Recursively convert dataclasses / Decimals / dates / enums into JSON-safe values."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [to_jsonable(v) for v in value]
    return value


class Serializable:
    """Mixin giving dataclasses a JSON-serializable ``to_dict()`` (Decimals -> str)."""

    def to_dict(self) -> dict[str, Any]:
        result = to_jsonable(self)
        assert isinstance(result, dict)
        return result


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MarkRecord(Serializable):
    student_id: int
    subject_id: int
    marks: Decimal | None
    is_absent: bool = False


@dataclass(frozen=True)
class SubjectConfig(Serializable):
    subject_id: int
    name: str
    max_marks: Decimal
    pass_marks: Decimal


@dataclass(frozen=True)
class StudentInfo(Serializable):
    student_id: int
    pseudo_id: str
    full_name: str
    class_section_id: int
    class_label: str


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubjectResult(Serializable):
    subject_id: int
    subject_name: str
    marks: Decimal | None
    max_marks: Decimal
    pass_marks: Decimal
    is_absent: bool
    is_missing: bool
    passed: bool
    percentage: Decimal  # 0 when absent/missing


@dataclass(frozen=True)
class StudentResult(Serializable):
    student_id: int
    pseudo_id: str
    full_name: str
    class_section_id: int
    class_label: str
    subjects: list[SubjectResult]
    total: Decimal
    max_total: Decimal
    percentage: Decimal
    passed: bool
    appeared: bool
    failed_subjects: list[int]  # subject ids, in config order
    rank_in_section: int
    section_size: int

    @property
    def failed_count(self) -> int:
        return len(self.failed_subjects)

    def subject(self, subject_id: int) -> SubjectResult | None:
        return next((s for s in self.subjects if s.subject_id == subject_id), None)


@dataclass(frozen=True)
class DistributionBand(Serializable):
    label: str
    lower: Decimal
    upper: Decimal
    count: int


@dataclass(frozen=True)
class ClassSummary(Serializable):
    class_section_id: int | None  # None = combined group (e.g. whole school)
    class_label: str
    student_count: int
    appeared_count: int
    pass_count: int
    fail_count: int
    pass_percentage: Decimal | None  # None when there are no students
    mean_percentage: Decimal | None  # over appeared students
    median_percentage: Decimal | None
    highest_percentage: Decimal | None
    lowest_percentage: Decimal | None
    distribution: list[DistributionBand]


@dataclass(frozen=True)
class SubjectStats(Serializable):
    student_count: int
    appeared_count: int  # has a mark (not absent, not missing)
    absent_count: int
    missing_count: int
    pass_count: int
    pass_percentage: Decimal | None  # over student_count
    mean_marks: Decimal | None  # over appeared
    mean_percentage: Decimal | None  # over appeared
    highest_marks: Decimal | None
    lowest_marks: Decimal | None


@dataclass(frozen=True)
class SectionSubjectStats(Serializable):
    class_section_id: int
    class_label: str
    stats: SubjectStats


@dataclass(frozen=True)
class SubjectSummary(Serializable):
    subject_id: int
    subject_name: str
    max_marks: Decimal
    pass_marks: Decimal
    overall: SubjectStats
    sections: list[SectionSubjectStats]
    weakest_sections: list[int]  # class_section_ids with the lowest pass %
    mean_percentage_change: Decimal | None = None  # vs previous exam, percentage points


@dataclass(frozen=True)
class SubjectChange(Serializable):
    subject_id: int
    subject_name: str
    previous_percentage: Decimal
    current_percentage: Decimal
    delta: Decimal


@dataclass(frozen=True)
class StudentChange(Serializable):
    student_id: int
    previous_percentage: Decimal
    current_percentage: Decimal
    delta: Decimal  # percentage points, current - previous
    subjects: list[SubjectChange] = field(default_factory=list)


@dataclass(frozen=True)
class RiskReason(Serializable):
    code: RiskCode
    detail: str
    evidence: dict[str, Any]


@dataclass(frozen=True)
class AtRiskStudent(Serializable):
    student_id: int
    pseudo_id: str
    full_name: str
    class_section_id: int
    class_label: str
    percentage: Decimal
    failed_subject_count: int
    delta: Decimal | None  # vs previous exam, when known
    severity: Severity
    reasons: list[RiskReason]


# ---------------------------------------------------------------------------
# Student results
# ---------------------------------------------------------------------------


def _subject_result(cfg: SubjectConfig, record: MarkRecord | None) -> SubjectResult:
    is_absent = bool(record and record.is_absent)
    marks = None if record is None or is_absent else record.marks
    is_missing = not is_absent and marks is None
    passed = marks is not None and marks >= cfg.pass_marks
    percentage = _pct(marks, cfg.max_marks) if marks is not None else quantize(ZERO)
    return SubjectResult(
        subject_id=cfg.subject_id,
        subject_name=cfg.name,
        marks=marks,
        max_marks=cfg.max_marks,
        pass_marks=cfg.pass_marks,
        is_absent=is_absent,
        is_missing=is_missing,
        passed=passed,
        percentage=percentage,
    )


def _competition_ranks(percentages: Sequence[Decimal]) -> list[int]:
    """Competition ranking (1, 2, 2, 4) by value descending, aligned to the input order."""
    order = sorted(range(len(percentages)), key=lambda i: percentages[i], reverse=True)
    ranks = [0] * len(percentages)
    for position, idx in enumerate(order):
        if position > 0 and percentages[idx] == percentages[order[position - 1]]:
            ranks[idx] = ranks[order[position - 1]]
        else:
            ranks[idx] = position + 1
    return ranks


def student_results(
    students: Sequence[StudentInfo],
    configs: Sequence[SubjectConfig],
    marks: Iterable[MarkRecord],
) -> list[StudentResult]:
    """Compute every student's result. Output order: section (first appearance), rank, pseudo id."""
    by_key: dict[tuple[int, int], MarkRecord] = {(m.student_id, m.subject_id): m for m in marks}
    max_total = sum((c.max_marks for c in configs), ZERO)

    partial: list[tuple[StudentInfo, list[SubjectResult], Decimal, Decimal]] = []
    for student in students:
        subject_rows = [
            _subject_result(c, by_key.get((student.student_id, c.subject_id))) for c in configs
        ]
        obtained = sum((s.marks for s in subject_rows if s.marks is not None), ZERO)
        partial.append((student, subject_rows, obtained, _pct(obtained, max_total)))

    section_order: dict[int, int] = {}
    by_section: dict[int, list[int]] = defaultdict(list)
    for idx, (student, _, _, _) in enumerate(partial):
        section_order.setdefault(student.class_section_id, len(section_order))
        by_section[student.class_section_id].append(idx)

    ranks: dict[int, tuple[int, int]] = {}
    for indices in by_section.values():
        section_ranks = _competition_ranks([partial[i][3] for i in indices])
        for i, rank in zip(indices, section_ranks, strict=True):
            ranks[i] = (rank, len(indices))

    results: list[StudentResult] = []
    for idx, (info, subjects, total, percentage) in enumerate(partial):
        rank, size = ranks[idx]
        results.append(
            StudentResult(
                student_id=info.student_id,
                pseudo_id=info.pseudo_id,
                full_name=info.full_name,
                class_section_id=info.class_section_id,
                class_label=info.class_label,
                subjects=subjects,
                total=quantize(total),
                max_total=quantize(max_total),
                percentage=percentage,
                passed=bool(subjects) and all(s.passed for s in subjects),
                appeared=any(s.marks is not None for s in subjects),
                failed_subjects=[s.subject_id for s in subjects if not s.passed],
                rank_in_section=rank,
                section_size=size,
            )
        )
    results.sort(key=lambda r: (section_order[r.class_section_id], r.rank_in_section, r.pseudo_id))
    return results


# ---------------------------------------------------------------------------
# Class / group summary
# ---------------------------------------------------------------------------


def _band_index(percentage: Decimal) -> int:
    for idx, (_, lower, upper) in enumerate(DISTRIBUTION_BANDS):
        last = idx == len(DISTRIBUTION_BANDS) - 1
        if lower <= percentage < upper or (last and percentage == upper):
            return idx
    # Out of range (e.g. bad data > 100): clamp to the nearest band.
    return 0 if percentage < 0 else len(DISTRIBUTION_BANDS) - 1


def class_summary(
    results: Sequence[StudentResult],
    class_section_id: int | None = None,
    class_label: str = "All classes",
) -> ClassSummary:
    """Summarise a group of results (a section, or several sections combined)."""
    appeared = [r.percentage for r in results if r.appeared]
    pass_count = sum(1 for r in results if r.passed)
    counts = [0] * len(DISTRIBUTION_BANDS)
    for pct in appeared:
        counts[_band_index(pct)] += 1
    return ClassSummary(
        class_section_id=class_section_id,
        class_label=class_label,
        student_count=len(results),
        appeared_count=len(appeared),
        pass_count=pass_count,
        fail_count=len(results) - pass_count,
        pass_percentage=_count_pct(pass_count, len(results)),
        mean_percentage=_mean(appeared),
        median_percentage=_median(appeared),
        highest_percentage=max(appeared) if appeared else None,
        lowest_percentage=min(appeared) if appeared else None,
        distribution=[
            DistributionBand(label=label, lower=lower, upper=upper, count=counts[i])
            for i, (label, lower, upper) in enumerate(DISTRIBUTION_BANDS)
        ],
    )


# ---------------------------------------------------------------------------
# Subject summary
# ---------------------------------------------------------------------------


def subject_stats(entries: Sequence[SubjectResult]) -> SubjectStats:
    """Aggregate statistics over a set of per-student subject results."""
    with_marks = [e for e in entries if e.marks is not None]
    marks = [e.marks for e in with_marks if e.marks is not None]
    pass_count = sum(1 for e in entries if e.passed)
    return SubjectStats(
        student_count=len(entries),
        appeared_count=len(with_marks),
        absent_count=sum(1 for e in entries if e.is_absent),
        missing_count=sum(1 for e in entries if e.is_missing),
        pass_count=pass_count,
        pass_percentage=_count_pct(pass_count, len(entries)),
        mean_marks=_mean(marks),
        mean_percentage=_mean([e.percentage for e in with_marks]),
        highest_marks=quantize(max(marks)) if marks else None,
        lowest_marks=quantize(min(marks)) if marks else None,
    )


def subject_summary(
    results: Sequence[StudentResult],
    configs: Sequence[SubjectConfig],
    previous: Sequence[SubjectSummary] | None = None,
) -> list[SubjectSummary]:
    """Per-subject statistics overall and per section (sections in first-appearance order)."""
    previous_by_subject = {s.subject_id: s for s in previous or []}
    summaries: list[SubjectSummary] = []
    for cfg in configs:
        overall_entries: list[SubjectResult] = []
        per_section: dict[int, list[SubjectResult]] = {}
        labels: dict[int, str] = {}
        for r in results:
            entry = r.subject(cfg.subject_id)
            if entry is None:
                continue
            overall_entries.append(entry)
            per_section.setdefault(r.class_section_id, []).append(entry)
            labels[r.class_section_id] = r.class_label
        sections = [
            SectionSubjectStats(
                class_section_id=sid, class_label=labels[sid], stats=subject_stats(e)
            )
            for sid, e in per_section.items()
        ]
        rated = [s for s in sections if s.stats.pass_percentage is not None]
        weakest: list[int] = []
        if rated:
            lowest = min(
                s.stats.pass_percentage for s in rated if s.stats.pass_percentage is not None
            )
            weakest = [s.class_section_id for s in rated if s.stats.pass_percentage == lowest]
        overall = subject_stats(overall_entries)
        change: Decimal | None = None
        prev = previous_by_subject.get(cfg.subject_id)
        if (
            prev is not None
            and prev.overall.mean_percentage is not None
            and overall.mean_percentage is not None
        ):
            change = quantize(overall.mean_percentage - prev.overall.mean_percentage)
        summaries.append(
            SubjectSummary(
                subject_id=cfg.subject_id,
                subject_name=cfg.name,
                max_marks=cfg.max_marks,
                pass_marks=cfg.pass_marks,
                overall=overall,
                sections=sections,
                weakest_sections=weakest,
                mean_percentage_change=change,
            )
        )
    return summaries


# ---------------------------------------------------------------------------
# Comparison & at-risk
# ---------------------------------------------------------------------------


def compare_exams(
    prev_results: Sequence[StudentResult], curr_results: Sequence[StudentResult]
) -> list[StudentChange]:
    """Percentage-point change per student (and per shared subject), current minus previous."""
    prev_by_student = {r.student_id: r for r in prev_results}
    changes: list[StudentChange] = []
    for curr in curr_results:
        prev = prev_by_student.get(curr.student_id)
        if prev is None:
            continue
        prev_subjects = {s.subject_id: s for s in prev.subjects}
        subject_changes = [
            SubjectChange(
                subject_id=s.subject_id,
                subject_name=s.subject_name,
                previous_percentage=prev_subjects[s.subject_id].percentage,
                current_percentage=s.percentage,
                delta=quantize(s.percentage - prev_subjects[s.subject_id].percentage),
            )
            for s in curr.subjects
            if s.subject_id in prev_subjects
        ]
        changes.append(
            StudentChange(
                student_id=curr.student_id,
                previous_percentage=prev.percentage,
                current_percentage=curr.percentage,
                delta=quantize(curr.percentage - prev.percentage),
                subjects=subject_changes,
            )
        )
    return changes


def _failed_reason(result: StudentResult) -> RiskReason:
    failed = [s for s in result.subjects if not s.passed]
    names = ", ".join(s.subject_name for s in failed)
    noun = "subject" if len(failed) == 1 else "subjects"
    return RiskReason(
        code="FAILED_SUBJECTS",
        detail=f"Failed {len(failed)} {noun}: {names}",
        evidence={
            "count": len(failed),
            "subjects": [
                {
                    "subject_id": s.subject_id,
                    "subject_name": s.subject_name,
                    "marks": str(s.marks) if s.marks is not None else None,
                    "pass_marks": str(s.pass_marks),
                    "max_marks": str(s.max_marks),
                    "is_absent": s.is_absent,
                    "is_missing": s.is_missing,
                }
                for s in failed
            ],
        },
    )


def at_risk_students(
    curr_results: Sequence[StudentResult],
    changes: Sequence[StudentChange] | None = None,
) -> list[AtRiskStudent]:
    """Apply the at-risk rule. Sorted: high severity first, then lowest percentage, pseudo id."""
    change_by_student = {c.student_id: c for c in changes or []}
    flagged: list[AtRiskStudent] = []
    for r in curr_results:
        reasons: list[RiskReason] = []
        if r.failed_subjects:
            reasons.append(_failed_reason(r))
        change = change_by_student.get(r.student_id)
        if change is not None and change.delta <= -AT_RISK_DROP_POINTS:
            reasons.append(
                RiskReason(
                    code="SHARP_DROP",
                    detail=(
                        f"Dropped {abs(change.delta)} points vs previous exam "
                        f"({change.previous_percentage}% -> {change.current_percentage}%)"
                    ),
                    evidence={
                        "previous_percentage": str(change.previous_percentage),
                        "current_percentage": str(change.current_percentage),
                        "delta": str(change.delta),
                        "threshold_points": str(AT_RISK_DROP_POINTS),
                    },
                )
            )
        if r.percentage < LOW_OVERALL_THRESHOLD:
            reasons.append(
                RiskReason(
                    code="LOW_OVERALL",
                    detail=f"Overall {r.percentage}% is below {LOW_OVERALL_THRESHOLD}%",
                    evidence={
                        "percentage": str(r.percentage),
                        "threshold": str(LOW_OVERALL_THRESHOLD),
                    },
                )
            )
        if not reasons:
            continue
        severity: Severity = (
            "high"
            if len(reasons) >= 2 or r.failed_count >= HIGH_SEVERITY_FAILED_SUBJECTS
            else "medium"
        )
        flagged.append(
            AtRiskStudent(
                student_id=r.student_id,
                pseudo_id=r.pseudo_id,
                full_name=r.full_name,
                class_section_id=r.class_section_id,
                class_label=r.class_label,
                percentage=r.percentage,
                failed_subject_count=r.failed_count,
                delta=change.delta if change is not None else None,
                severity=severity,
                reasons=reasons,
            )
        )
    flagged.sort(key=lambda a: (a.severity != "high", a.percentage, a.pseudo_id))
    return flagged
