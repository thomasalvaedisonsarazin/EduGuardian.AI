"""Orchestrator graph end-to-end on the seeded demo school (template + fake-LLM modes)."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.agents.graph import run_graph
from app.agents.intervention import (
    ExamContext,
    StudentCase,
    draft_with_template,
    render_plan_text,
)
from app.agents.orchestrator import start_run
from app.analytics.service import exam_overview
from app.config import Settings
from app.dependencies import TenantContext
from app.llm.client import LLMClient
from app.models import (
    AgentRun,
    AgentRunStatus,
    AgentStep,
    AuditLog,
    Exam,
    InterventionPlan,
    InterventionStatus,
    Mark,
    Membership,
    MembershipRole,
    Report,
    ReportFormat,
    ReportKind,
    Student,
    User,
)
from app.seed.demo import seed_demo

AGENTS = [
    "DataQualityAgent",
    "PerformanceAnalysisAgent",
    "InterventionAgent",
    "ReportingAgent",
    "Orchestrator",
]
TODAY = date(2026, 10, 16)


@pytest.fixture()
def demo(db: Session) -> dict[str, Any]:
    summary = seed_demo(db, sample_dir=None, commit=False)
    school_id = summary.school_id
    admin = db.scalar(
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.school_id == school_id, Membership.role == MembershipRole.school_admin)
    )
    assert admin is not None
    exam = db.scalar(select(Exam).where(Exam.school_id == school_id, Exam.sequence == 2))
    assert exam is not None
    ctx = TenantContext(user=admin, school_id=school_id, role=MembershipRole.school_admin)
    return {"school_id": school_id, "exam": exam, "ctx": ctx}


def fake_report(db: Session, **kw: Any) -> Report:
    report = Report(
        school_id=kw["school_id"],
        run_id=kw["run_id"],
        kind=ReportKind(kw["kind"]),
        format=ReportFormat(kw["fmt"]),
        file_path=f"fake/{kw['run_id']}.{ReportFormat(kw['fmt']).value}",
        created_by=kw["created_by"],
    )
    db.add(report)
    db.flush()
    return report


def run(db: Session, demo: dict[str, Any], **kwargs: Any) -> AgentRun:
    queued = start_run(db, demo["ctx"], demo["exam"].id, kwargs.pop("sections", None))
    kwargs.setdefault("report_fn", fake_report)
    kwargs.setdefault("llm_factory", lambda _db, _sid: None)
    result = run_graph(db, queued.id, today=lambda: TODAY, **kwargs)
    assert result is not None
    return result


def steps_of(db: Session, run_id: int) -> list[AgentStep]:
    return list(
        db.scalars(select(AgentStep).where(AgentStep.run_id == run_id).order_by(AgentStep.id))
    )


def plans_of(db: Session, run_id: int) -> list[InterventionPlan]:
    return list(db.scalars(select(InterventionPlan).where(InterventionPlan.run_id == run_id)))


# --- template mode -------------------------------------------------------------------------


def test_graph_template_mode_end_to_end(db: Session, demo: dict[str, Any]) -> None:
    result = run(db, demo)
    assert result.status == AgentRunStatus.awaiting_approval
    assert result.finished_at is not None and result.error is None

    steps = steps_of(db, result.id)
    assert [s.agent_name for s in steps] == AGENTS
    assert all(s.status.value == "done" for s in steps)
    assert all(s.started_at and s.finished_at for s in steps)

    overview = exam_overview(db, demo["school_id"], demo["exam"].id)
    at_risk_ids = {a.student_id for a in overview.at_risk}
    plans = plans_of(db, result.id)
    assert at_risk_ids and {p.student_id for p in plans} == at_risk_ids
    assert len(plans) == len(at_risk_ids)

    analysis = steps[1].output_summary or {}
    assert analysis["at_risk_total"] == len(at_risk_ids)
    assert sum(analysis["at_risk_by_severity"].values()) == len(at_risk_ids)
    assert len(analysis["weakest_subjects"]) == 3

    drafting = steps[2].output_summary or {}
    assert drafting["mode"] == "template" and drafting["plans_created"] == len(plans)
    assert drafting["tokens"] == 0 and result.token_usage == 0

    plan = plans[0]
    assert plan.status == InterventionStatus.draft
    assert plan.evidence and plan.evidence["exam_id"] == demo["exam"].id
    assert plan.evidence["reasons"] and plan.evidence["draft"]["mode"] == "template"
    assert plan.activities and {"title", "description", "frequency", "owner"} <= set(
        plan.activities[0]
    )
    assert plan.reassess_on is not None and plan.reassess_on > TODAY
    assert "Activities:" in plan.plan_text

    reports = steps[3].output_summary or {}
    assert [r["format"] for r in reports["reports"]] == ["pdf", "xlsx"]

    actors = set(
        db.scalars(
            select(AuditLog.actor).where(
                AuditLog.entity_type == "agent_run", AuditLog.entity_id == result.id
            )
        )
    )
    assert set(AGENTS) <= actors and "user" in actors
    drafted = db.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.action == "plan_drafted", AuditLog.school_id == demo["school_id"]
        )
    )
    assert drafted == len(plans)


def test_rerun_is_idempotent(db: Session, demo: dict[str, Any]) -> None:
    first = run(db, demo)
    n = len(plans_of(db, first.id))
    second = run(db, demo)
    assert plans_of(db, second.id) == []
    assert second.status == AgentRunStatus.done  # nothing new to approve
    drafting = steps_of(db, second.id)[2].output_summary or {}
    assert drafting["skipped_existing"] == n and drafting["plans_created"] == 0

    # a rejected plan is re-drafted on the next run
    rejected = plans_of(db, first.id)[0]
    rejected.status = InterventionStatus.rejected
    db.commit()
    third = run(db, demo)
    assert [p.student_id for p in plans_of(db, third.id)] == [rejected.student_id]


def test_section_filter_limits_plans(db: Session, demo: dict[str, Any]) -> None:
    student = db.scalar(select(Student).where(Student.school_id == demo["school_id"]))
    assert student is not None
    result = run(db, demo, sections=[student.class_section_id])
    sections = set(
        db.scalars(
            select(Student.class_section_id).where(
                Student.id.in_([p.student_id for p in plans_of(db, result.id)])
            )
        )
    )
    assert sections == {student.class_section_id}


def test_no_marks_fails_run_cleanly(db: Session, demo: dict[str, Any]) -> None:
    db.execute(delete(Mark).where(Mark.exam_id == demo["exam"].id))
    db.commit()
    result = run(db, demo)
    assert result.status == AgentRunStatus.failed
    assert result.error and "No committed marks" in result.error
    steps = steps_of(db, result.id)
    assert [s.agent_name for s in steps] == ["DataQualityAgent"]
    assert steps[0].status.value == "failed" and steps[0].error


def test_report_failure_is_soft(db: Session, demo: dict[str, Any]) -> None:
    def broken(_db: Session, **_: Any) -> Report:
        raise RuntimeError("disk full")

    result = run(db, demo, report_fn=broken)
    assert result.status == AgentRunStatus.awaiting_approval
    steps = {s.agent_name: s for s in steps_of(db, result.id)}
    assert steps["ReportingAgent"].status.value == "failed"
    assert "disk full" in (steps["ReportingAgent"].error or "")
    assert steps["Orchestrator"].status.value == "done"
    assert any(
        "ReportingAgent" in w for w in (steps["Orchestrator"].output_summary or {})["warnings"]
    )


def test_real_report_generator(
    db: Session, demo: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    generator = pytest.importorskip("app.reports.generator")
    from app.config import settings

    monkeypatch.setattr(settings, "REPORTS_DIR", str(tmp_path))
    result = run(db, demo, report_fn=generator.generate_report)
    step = {s.agent_name: s for s in steps_of(db, result.id)}["ReportingAgent"]
    assert step.status.value == "done", step.error
    assert db.scalar(select(func.count(Report.id)).where(Report.run_id == result.id)) == 2


# --- LLM mode with a fake OpenAI SDK --------------------------------------------------------


class FakeLLMCompletions:
    """Answers with a valid plan for every pseudo id in the request (optionally sabotaged)."""

    def __init__(self, mode: str = "valid") -> None:
        self.mode = mode
        self.requests: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.requests.append(kwargs)
        payload = json.loads(kwargs["messages"][1]["content"])
        ids = [s["pseudo_id"] for s in payload["students"]]
        plans = [
            {
                "pseudo_id": pid,
                "summary": "Build confidence with short weekly goals.",
                "focus_areas": ["Core concepts"],
                "activities": [
                    {
                        "title": "Peer study",
                        "description": "Work through practice questions with a peer.",
                        "frequency": "Twice a week",
                        "owner": "student",
                    }
                ],
                "reassess_after_weeks": 4,
                "rationale": "Marks below the pass mark as shown in the evidence.",
            }
            for pid in ids
        ]
        if self.mode == "invalid_json":
            content = "{not json"
        elif self.mode == "one_bad":
            plans[0]["activities"][0]["owner"] = "principal"  # invalid enum -> fallback
            content = json.dumps({"plans": plans})
        elif self.mode == "unsafe":
            plans[0]["summary"] = "Possible ADHD diagnosis."
            content = json.dumps({"plans": plans})
        else:
            content = json.dumps({"plans": plans})
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=2000, completion_tokens=1000),
        )


def llm_factory(completions: FakeLLMCompletions, **overrides: Any) -> Any:
    config = Settings(
        LLM_ENABLED=True,
        OPENAI_API_KEY="sk-test",
        LLM_BATCH_SIZE=8,
        **overrides,
    )

    def factory(db: Session, school_id: int) -> LLMClient:
        return LLMClient(
            db,
            school_id,
            config=config,
            sdk_client=SimpleNamespace(chat=SimpleNamespace(completions=completions)),
        )

    return factory


def test_llm_mode_batches_and_tracks_cost(
    db: Session, demo: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.agents.intervention.settings.LLM_BATCH_SIZE", 8)
    fake = FakeLLMCompletions()
    result = run(db, demo, llm_factory=llm_factory(fake))
    plans = plans_of(db, result.id)
    expected_calls = -(-len(plans) // 8)
    assert len(fake.requests) == expected_calls
    drafting = steps_of(db, result.id)[2].output_summary or {}
    assert drafting["mode"] == "llm" and drafting["llm_plans"] == len(plans)
    assert result.token_usage == 3000 * expected_calls
    assert Decimal(result.cost_usd) > 0
    assert all((p.evidence or {})["draft"]["mode"] == "llm" for p in plans)
    assert plans[0].activities == [
        {
            "title": "Peer study",
            "description": "Work through practice questions with a peer.",
            "frequency": "Twice a week",
            "owner": "student",
        }
    ]


def test_llm_payload_contains_no_pii(db: Session, demo: dict[str, Any]) -> None:
    fake = FakeLLMCompletions()
    run(db, demo, llm_factory=llm_factory(fake))
    assert fake.requests
    students = db.execute(
        select(Student.full_name, Student.admission_no).where(
            Student.school_id == demo["school_id"]
        )
    ).all()
    sent = json.dumps([r["messages"] for r in fake.requests]).lower()
    for name, admission_no in students:
        assert name.lower() not in sent
        assert admission_no.lower() not in sent
    assert "s-00" in sent  # pseudonymous ids are what identifies students


def test_llm_invalid_json_falls_back_to_template(db: Session, demo: dict[str, Any]) -> None:
    result = run(db, demo, llm_factory=llm_factory(FakeLLMCompletions("invalid_json")))
    plans = plans_of(db, result.id)
    assert plans and all((p.evidence or {})["draft"]["mode"] == "template" for p in plans)
    drafting = steps_of(db, result.id)[2].output_summary or {}
    assert drafting["mode"] == "template"
    assert {f["reason"] for f in drafting["fallbacks"]} == {"invalid_json"}
    assert result.token_usage > 0  # billed calls are still accounted for


@pytest.mark.parametrize("mode", ["one_bad", "unsafe"])
def test_llm_invalid_item_falls_back_per_student(
    db: Session, demo: dict[str, Any], mode: str
) -> None:
    result = run(db, demo, llm_factory=llm_factory(FakeLLMCompletions(mode)))
    drafting = steps_of(db, result.id)[2].output_summary or {}
    assert drafting["mode"] == "mixed"
    assert drafting["template_plans"] == drafting["llm_calls"]  # first student of each batch
    plans = plans_of(db, result.id)
    assert not any("ADHD" in p.plan_text for p in plans)


def test_llm_budget_exceeded_falls_back(db: Session, demo: dict[str, Any]) -> None:
    fake = FakeLLMCompletions()
    result = run(db, demo, llm_factory=llm_factory(fake, LLM_MONTHLY_BUDGET_USD=0.0))
    assert fake.requests == []
    drafting = steps_of(db, result.id)[2].output_summary or {}
    assert drafting["mode"] == "template"
    assert {f["reason"] for f in drafting["fallbacks"]} == {"budget_exceeded"}
    assert "budget" in (drafting["note"] or "").lower()
    assert result.status == AgentRunStatus.awaiting_approval


# --- template rules ------------------------------------------------------------------------


def test_template_rules_are_supportive_and_cite_evidence(db: Session, demo: dict[str, Any]) -> None:
    overview = exam_overview(db, demo["school_id"], demo["exam"].id)
    results = {r.student_id: r for r in overview.results}
    context = ExamContext("Quarterly Exam", "Unit Test 1")
    seen_codes: set[str] = set()
    for at in overview.at_risk:
        case = StudentCase.from_analysis(at, results[at.student_id])
        plan = draft_with_template(case, context)
        text = render_plan_text(plan)
        codes = {r.code for r in at.reasons}
        seen_codes |= codes
        titles = {a.title for a in plan.activities}
        if "SHARP_DROP" in codes:
            assert "Check-in conversation" in titles
        if "LOW_OVERALL" in codes:
            assert "Study-skills plan" in titles
        for s in case.failed_subjects[:3]:
            assert any(s.subject_name in t for t in titles)
            assert s.subject_name in plan.rationale
        assert at.full_name not in text
        assert "punish" not in text.lower() and "diagnos" not in text.lower()
    assert {"FAILED_SUBJECTS", "SHARP_DROP"} <= seen_codes
