"""Intervention Agent - drafts supportive, evidence-based plans for at-risk students.

Input per student is a :class:`StudentCase` built from the deterministic analytics
(:class:`~app.analytics.calculations.AtRiskStudent` + the student's per-subject results). The
agent never computes numbers itself; it only turns computed findings into an action plan.

Two implementations share one output model (:class:`PlanDraft`):

* :func:`draft_with_template` - deterministic rules (always available):
    - per failed subject -> targeted practice + remedial session (make-up assessment if absent);
    - sharp drop -> check-in conversation + revision plan;
    - low overall -> study-skills plan + fortnightly progress review.
* :func:`draft_with_llm` - batched LLM calls (<= ``LLM_BATCH_SIZE`` students per call) with a
  strict JSON schema, validated with Pydantic. Any student whose plan is missing, invalid or
  unsafe falls back to the template; LLM unavailable / budget exceeded falls back for the
  remaining students.

Privacy: LLM payloads contain the pseudonymous id, class label, marks and computed evidence only
(see :meth:`StudentCase.to_llm_payload`); every request is checked by ``assert_no_pii``.
Plans are supportive and non-punitive and never contain diagnoses.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.analytics.calculations import AtRiskStudent, RiskReason, StudentResult, SubjectResult
from app.config import settings
from app.exceptions import BudgetExceededError
from app.llm.client import JsonLLM, LLMResponseError, LLMUnavailable
from app.llm.privacy import PIIViolationError

logger = logging.getLogger(__name__)

AGENT_NAME = "InterventionAgent"

Owner = Literal["teacher", "student", "parent"]
DraftMode = Literal["llm", "template"]

MAX_TEMPLATE_SUBJECTS = 3
MAX_ACTIVITIES = 8
HIGH_SEVERITY_WEEKS = 4
DEFAULT_WEEKS = 6

# Language a supportive school plan must never contain (diagnoses, labels, punishment).
UNSAFE_PATTERNS = re.compile(
    r"\b(diagnos\w*|adhd|dyslexi\w*|dyscalculi\w*|autis\w*|disorder\w*|disabilit\w*|"
    r"depress\w*|anxiety disorder|lazy|stupid|punish\w*|detention|expel\w*|suspen\w*|"
    r"medicat\w*)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------


class Activity(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=600)
    frequency: str = Field(min_length=1, max_length=80)
    owner: Owner


class PlanDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    summary: str = Field(min_length=1, max_length=600)
    focus_areas: list[str] = Field(min_length=1, max_length=6)
    activities: list[Activity] = Field(min_length=1, max_length=8)
    reassess_after_weeks: int = Field(ge=1, le=12)
    rationale: str = Field(min_length=1, max_length=1200)


class LLMPlanItem(PlanDraft):
    pseudo_id: str


class LLMBatchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    plans: list[dict[str, Any]]


#: Strict JSON schema sent with ``response_format`` (OpenAI structured outputs).
_ACTIVITY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "description", "frequency", "owner"],
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "frequency": {"type": "string"},
        "owner": {"type": "string", "enum": ["teacher", "student", "parent"]},
    },
}
PLAN_BATCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["plans"],
    "properties": {
        "plans": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "pseudo_id",
                    "summary",
                    "focus_areas",
                    "activities",
                    "reassess_after_weeks",
                    "rationale",
                ],
                "properties": {
                    "pseudo_id": {"type": "string"},
                    "summary": {"type": "string"},
                    "focus_areas": {"type": "array", "items": {"type": "string"}},
                    "activities": {"type": "array", "items": _ACTIVITY_SCHEMA},
                    "reassess_after_weeks": {"type": "integer"},
                    "rationale": {"type": "string"},
                },
            },
        }
    },
}

SYSTEM_PROMPT = """You are an experienced, caring school academic coordinator.
For each student case you receive, draft a short, practical support plan for the next few weeks.

Rules:
- Students are identified only by a pseudonymous id (e.g. S-0042). Use "the student";
  never invent names.
- Base every statement on the evidence provided (marks, pass marks, changes in percentage points).
  Do not invent or recompute numbers; quote the numbers given.
- Be supportive, encouraging and non-punitive. No blame, no punishment, no labels.
- Never diagnose or speculate about medical, psychological or learning conditions.
- Activities must be concrete and realistic for a school: who does it (owner: teacher, student or
  parent), what, and how often.
- 2 to 6 activities per student; reassess_after_weeks between 2 and 8.
- rationale must cite the specific evidence (subject marks vs pass marks, percentage drop,
  overall percentage).
Return JSON: {"plans": [ ... one object per student, same pseudo_id as the input ... ]}."""


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExamContext:
    exam_name: str
    previous_exam_name: str | None = None


@dataclass(frozen=True)
class StudentCase:
    """Everything the agent may know about one at-risk student (no direct identifiers)."""

    student_id: int  # internal only - never sent to the LLM
    pseudo_id: str
    class_label: str
    percentage: Decimal
    delta: Decimal | None
    severity: str
    reasons: list[RiskReason]
    subjects: list[SubjectResult] = field(default_factory=list)

    @classmethod
    def from_analysis(cls, at_risk: AtRiskStudent, result: StudentResult | None) -> StudentCase:
        return cls(
            student_id=at_risk.student_id,
            pseudo_id=at_risk.pseudo_id,
            class_label=at_risk.class_label,
            percentage=at_risk.percentage,
            delta=at_risk.delta,
            severity=at_risk.severity,
            reasons=list(at_risk.reasons),
            subjects=list(result.subjects) if result is not None else [],
        )

    def reason(self, code: str) -> RiskReason | None:
        return next((r for r in self.reasons if r.code == code), None)

    @property
    def failed_subjects(self) -> list[SubjectResult]:
        return [s for s in self.subjects if not s.passed]

    def to_llm_payload(self) -> dict[str, Any]:
        """Pseudonymous payload: pseudo id, class, marks and computed evidence only."""
        return {
            "pseudo_id": self.pseudo_id,
            "class": self.class_label,
            "overall_percentage": str(self.percentage),
            "change_vs_previous_exam_points": str(self.delta) if self.delta is not None else None,
            "severity": self.severity,
            "reasons": [
                {"code": r.code, "detail": r.detail, "evidence": r.evidence} for r in self.reasons
            ],
            "subjects": [
                {
                    "subject": s.subject_name,
                    "marks": str(s.marks) if s.marks is not None else None,
                    "max_marks": str(s.max_marks),
                    "pass_marks": str(s.pass_marks),
                    "absent": s.is_absent,
                    "missing": s.is_missing,
                    "passed": s.passed,
                }
                for s in self.subjects
            ],
        }


@dataclass
class DraftOutcome:
    plans: dict[str, PlanDraft] = field(default_factory=dict)  # by pseudo_id
    modes: dict[str, DraftMode] = field(default_factory=dict)
    fallbacks: list[dict[str, str]] = field(default_factory=list)
    tokens: int = 0
    cost_usd: Decimal = Decimal(0)
    llm_calls: int = 0
    model: str | None = None
    note: str | None = None  # why the LLM was not used at all

    @property
    def mode(self) -> str:
        used = set(self.modes.values())
        if not used:
            return "none"
        if used == {"llm"}:
            return "llm"
        if used == {"template"}:
            return "template"
        return "mixed"

    def count(self, mode: DraftMode) -> int:
        return sum(1 for m in self.modes.values() if m == mode)


# ---------------------------------------------------------------------------
# Template drafting (deterministic)
# ---------------------------------------------------------------------------


def _fmt(value: Decimal | str | None) -> str:
    if value is None:
        return "-"
    try:
        d = Decimal(str(value))
    except ArithmeticError:
        return str(value)
    return f"{d.normalize():f}" if d == d.to_integral() else f"{d:.2f}".rstrip("0").rstrip(".")


def _subject_evidence(s: SubjectResult) -> str:
    if s.is_absent:
        return f"{s.subject_name}: absent (pass mark {_fmt(s.pass_marks)}/{_fmt(s.max_marks)})"
    if s.is_missing or s.marks is None:
        return f"{s.subject_name}: no mark recorded"
    return f"{s.subject_name}: {_fmt(s.marks)}/{_fmt(s.max_marks)} (pass mark {_fmt(s.pass_marks)})"


def _failed_from_evidence(case: StudentCase) -> list[dict[str, Any]]:
    reason = case.reason("FAILED_SUBJECTS")
    if reason is None:
        return []
    subjects = reason.evidence.get("subjects", [])
    return [s for s in subjects if isinstance(s, dict)]


def draft_with_template(case: StudentCase, context: ExamContext) -> PlanDraft:
    """Deterministic, rule-based plan (see module docstring)."""
    activities: list[Activity] = []
    focus: list[str] = []
    evidence: list[str] = []

    failed = case.failed_subjects
    # fall back to the stored evidence when per-subject results are absent
    failed_ev = _failed_from_evidence(case) if not failed else []
    failed_names = [s.subject_name for s in failed] or [
        str(s.get("subject_name", "subject")) for s in failed_ev
    ]

    for s in failed[:MAX_TEMPLATE_SUBJECTS]:
        evidence.append(_subject_evidence(s))
        if s.is_absent or s.is_missing:
            focus.append(f"Catch up on {s.subject_name}")
            activities.append(
                Activity(
                    title=f"Make-up assessment in {s.subject_name}",
                    description=(
                        f"Arrange a make-up assessment for {s.subject_name} and share the "
                        "topics covered so the student can prepare."
                    ),
                    frequency="Once, within 2 weeks",
                    owner="teacher",
                )
            )
        else:
            focus.append(f"{s.subject_name} fundamentals")
            activities.append(
                Activity(
                    title=f"Targeted practice in {s.subject_name}",
                    description=(
                        f"Short practice sets on the {s.subject_name} topics where marks were "
                        f"lost in {context.exam_name}; review answers with the teacher."
                    ),
                    frequency="3 times a week, 20 minutes",
                    owner="student",
                )
            )
            activities.append(
                Activity(
                    title=f"Remedial session in {s.subject_name}",
                    description=(
                        f"Small-group or one-to-one session to re-teach key {s.subject_name} "
                        "concepts and check understanding with a few quick questions."
                    ),
                    frequency="Weekly",
                    owner="teacher",
                )
            )
    if not failed and failed_ev:
        for ev in failed_ev[:MAX_TEMPLATE_SUBJECTS]:
            name = str(ev.get("subject_name", "the subject"))
            marks = ev.get("marks") or "absent"
            evidence.append(f"{name}: {marks} (pass mark {ev.get('pass_marks')})")
            focus.append(f"{name} fundamentals")
            activities.append(
                Activity(
                    title=f"Targeted practice in {name}",
                    description=f"Short practice sets on the {name} topics where marks were lost.",
                    frequency="3 times a week, 20 minutes",
                    owner="student",
                )
            )
    if len(failed_names) > MAX_TEMPLATE_SUBJECTS:
        rest = ", ".join(failed_names[MAX_TEMPLATE_SUBJECTS:])
        evidence.append(f"Also below the pass mark in: {rest}")

    subject_activities = activities
    activities = []  # reason-based activities (always kept within the cap)
    drop = case.reason("SHARP_DROP")
    if drop is not None:
        prev = drop.evidence.get("previous_percentage")
        curr = drop.evidence.get("current_percentage")
        delta = drop.evidence.get("delta")
        since = f" since {context.previous_exam_name}" if context.previous_exam_name else ""
        evidence.append(
            f"Overall result changed by {_fmt(delta)} points{since} "
            f"({_fmt(prev)}% -> {_fmt(curr)}%)"
        )
        focus.append("Regain previous performance")
        activities.append(
            Activity(
                title="Check-in conversation",
                description=(
                    "A friendly one-to-one conversation to understand what changed since the "
                    "last exam and agree on two or three small goals together."
                ),
                frequency="Once in the first week, then as needed",
                owner="teacher",
            )
        )
        activities.append(
            Activity(
                title="Weekly revision plan",
                description=(
                    "Use a simple weekly timetable to revise the topics of the last exam, "
                    "ticking off each topic once practised."
                ),
                frequency="Weekly",
                owner="student",
            )
        )

    low = case.reason("LOW_OVERALL")
    if low is not None:
        evidence.append(
            f"Overall {_fmt(low.evidence.get('percentage'))}% is below the "
            f"{_fmt(low.evidence.get('threshold'))}% threshold"
        )
        focus.append("Study skills and routine")
        activities.append(
            Activity(
                title="Study-skills plan",
                description=(
                    "Introduce a daily study routine with a planner: short focused sessions, "
                    "note-making and self-testing on the day's lessons."
                ),
                frequency="Daily, 30 minutes",
                owner="student",
            )
        )
        activities.append(
            Activity(
                title="Progress review",
                description=(
                    "Review the planner and recent class work together and celebrate progress."
                ),
                frequency="Every 2 weeks",
                owner="teacher",
            )
        )

    if case.severity == "high" or len(activities) + len(subject_activities) < 2:
        activities.append(
            Activity(
                title="Encourage a regular study routine at home",
                description=(
                    "Provide a quiet time and place for homework and ask the student to share "
                    "one thing learned each week; contact the class teacher with any concerns."
                ),
                frequency="Weekly",
                owner="parent",
            )
        )

    # subject activities first, trimmed so the reason-based ones always fit in the cap
    room = max(0, MAX_ACTIVITIES - len(activities))
    if len(subject_activities) > room:  # keep one activity per subject before remedial ones
        primary = [a for a in subject_activities if not a.title.startswith("Remedial")]
        secondary = [a for a in subject_activities if a.title.startswith("Remedial")]
        subject_activities = primary + secondary
    activities = subject_activities[:room] + activities
    seen: set[str] = set()
    unique: list[Activity] = []
    for a in activities:
        if a.title not in seen:
            seen.add(a.title)
            unique.append(a)
    focus_unique = list(dict.fromkeys(focus))[:6] or ["Consolidate core skills"]

    weeks = HIGH_SEVERITY_WEEKS if case.severity == "high" else DEFAULT_WEEKS
    subjects_txt = ", ".join(failed_names[:MAX_TEMPLATE_SUBJECTS])
    if subjects_txt:
        summary = (
            f"Short-term support to help the student build confidence in {subjects_txt} "
            f"after {context.exam_name}, with a check of progress in {weeks} weeks."
        )
    else:
        summary = (
            f"Short-term support to help the student get back on track after "
            f"{context.exam_name}, with a check of progress in {weeks} weeks."
        )
    rationale = "Based on " + context.exam_name + " results: " + "; ".join(evidence) + "."
    return PlanDraft(
        summary=summary,
        focus_areas=focus_unique,
        activities=unique[:MAX_ACTIVITIES],
        reassess_after_weeks=weeks,
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# LLM drafting
# ---------------------------------------------------------------------------


def build_llm_request(cases: Sequence[StudentCase], context: ExamContext) -> str:
    """User message for one batch (pseudonymous)."""
    payload = {
        "exam": context.exam_name,
        "previous_exam": context.previous_exam_name,
        "students": [c.to_llm_payload() for c in cases],
    }
    return json.dumps(payload, ensure_ascii=False)


def _is_unsafe(plan: PlanDraft) -> bool:
    return bool(UNSAFE_PATTERNS.search(plan.model_dump_json()))


def _chunks(items: Sequence[StudentCase], size: int) -> list[Sequence[StudentCase]]:
    size = max(1, size)
    return [items[i : i + size] for i in range(0, len(items), size)]


def _template_fill(
    outcome: DraftOutcome,
    cases: Iterable[StudentCase],
    context: ExamContext,
    reason: str | None,
) -> None:
    for case in cases:
        if case.pseudo_id in outcome.plans:
            continue
        outcome.plans[case.pseudo_id] = draft_with_template(case, context)
        outcome.modes[case.pseudo_id] = "template"
        if reason is not None:
            outcome.fallbacks.append({"pseudo_id": case.pseudo_id, "reason": reason})


def draft_with_llm(
    cases: Sequence[StudentCase],
    context: ExamContext,
    client: JsonLLM,
    forbidden_terms: Iterable[str],
    batch_size: int | None = None,
) -> DraftOutcome:
    """Batched LLM drafting with per-student template fallback."""
    outcome = DraftOutcome(model=client.model)
    forbidden = set(forbidden_terms)
    batches = _chunks(cases, batch_size or settings.LLM_BATCH_SIZE)
    for index, batch in enumerate(batches):
        try:
            result = client.complete_json(
                system=SYSTEM_PROMPT,
                user=build_llm_request(batch, context),
                json_schema=PLAN_BATCH_SCHEMA,
                schema_name="intervention_plans",
                forbidden_terms=forbidden,
            )
        except (LLMUnavailable, BudgetExceededError) as exc:
            reason = (
                "budget_exceeded" if isinstance(exc, BudgetExceededError) else "llm_unavailable"
            )
            logger.warning("LLM drafting stopped at batch %d: %s", index, exc)
            remaining = [c for b in batches[index:] for c in b]
            _template_fill(outcome, remaining, context, reason)
            outcome.note = str(exc)
            return outcome
        except PIIViolationError:
            # Never send; fall back for this batch only (should be impossible by construction).
            _template_fill(outcome, batch, context, "pii_guard")
            continue
        except LLMResponseError as exc:
            if exc.usage is not None:
                outcome.tokens += exc.usage.total_tokens
                outcome.cost_usd += exc.usage.cost_usd
            outcome.llm_calls += 1
            _template_fill(outcome, batch, context, "invalid_json")
            continue

        outcome.llm_calls += 1
        outcome.tokens += result.usage.total_tokens
        outcome.cost_usd += result.usage.cost_usd
        try:
            items = LLMBatchResponse.model_validate(result.content).plans
        except ValidationError:
            _template_fill(outcome, batch, context, "invalid_schema")
            continue

        wanted = {c.pseudo_id for c in batch}
        for raw in items:
            try:
                item = LLMPlanItem.model_validate(raw)
            except ValidationError:
                continue  # its student falls back below
            if item.pseudo_id not in wanted or item.pseudo_id in outcome.plans:
                continue
            plan = PlanDraft.model_validate(item.model_dump(exclude={"pseudo_id"}))
            if _is_unsafe(plan):
                outcome.fallbacks.append({"pseudo_id": item.pseudo_id, "reason": "unsafe_language"})
                continue
            outcome.plans[item.pseudo_id] = plan
            outcome.modes[item.pseudo_id] = "llm"
        missing = [c for c in batch if c.pseudo_id not in outcome.plans]
        already = {f["pseudo_id"] for f in outcome.fallbacks}
        for case in missing:
            outcome.plans[case.pseudo_id] = draft_with_template(case, context)
            outcome.modes[case.pseudo_id] = "template"
            if case.pseudo_id not in already:
                outcome.fallbacks.append({"pseudo_id": case.pseudo_id, "reason": "invalid_plan"})
    return outcome


def draft_plans(
    cases: Sequence[StudentCase],
    context: ExamContext,
    client: JsonLLM | None,
    forbidden_terms: Iterable[str] = (),
    *,
    unavailable_reason: str | None = None,
) -> DraftOutcome:
    """Draft a plan for every case: LLM when a client is given, else templates."""
    if not cases:
        return DraftOutcome(model=client.model if client else None)
    if client is None:
        outcome = DraftOutcome(note=unavailable_reason or "LLM disabled - deterministic templates")
        _template_fill(outcome, cases, context, None)
        return outcome
    return draft_with_llm(cases, context, client, forbidden_terms)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

OWNER_LABELS: dict[str, str] = {"teacher": "Teacher", "student": "Student", "parent": "Parent"}


def render_plan_text(plan: PlanDraft) -> str:
    """Human-readable plan (stored in ``InterventionPlan.plan_text``; editable by staff)."""
    lines = [plan.summary, "", "Focus areas:"]
    lines += [f"- {area}" for area in plan.focus_areas]
    lines += ["", "Activities:"]
    for a in plan.activities:
        lines.append(f"- {a.title} ({OWNER_LABELS[a.owner]}, {a.frequency}): {a.description}")
    lines += ["", f"Reassess after {plan.reassess_after_weeks} weeks."]
    lines += ["", f"Why: {plan.rationale}"]
    return "\n".join(lines)
