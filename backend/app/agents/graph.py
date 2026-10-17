"""Orchestrator graph (LangGraph ``StateGraph``).

``data_quality -> performance_analysis -> intervention_drafting -> reporting -> finalize``

Every node writes an :class:`~app.models.AgentStep` (running -> done/failed, timestamps, input
and output summaries, error) and an :class:`~app.models.AuditLog` entry whose actor is the
agent's name, and commits after each step so the UI can poll live progress.

* A failing node marks its step and the run ``failed`` (with the error) and ends the graph -
  nothing is raised to the caller.
* The reporting node is *soft*: if report generation fails, its step is ``failed`` but the run
  still reaches ``awaiting_approval`` with a warning.

The database session and collaborators are injected through :class:`GraphDeps`, so tests run
the graph synchronously on their own session with a fake LLM / report generator.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from langgraph.graph import END, START, StateGraph
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents import data_quality as dq
from app.agents import intervention as iv
from app.agents.state import (
    DATA_QUALITY,
    INTERVENTION,
    ORCHESTRATOR,
    PERFORMANCE_ANALYSIS,
    REPORTING,
    RunState,
)
from app.analytics.calculations import to_jsonable
from app.analytics.service import ExamOverview, exam_overview
from app.config import settings
from app.exceptions import AppError
from app.llm.client import JsonLLM, LLMClient
from app.llm.privacy import forbidden_terms
from app.models import (
    AgentRun,
    AgentRunStatus,
    AgentStep,
    AgentStepStatus,
    Exam,
    ExamSubjectConfig,
    InterventionPlan,
    InterventionStatus,
    Mark,
    Student,
    Subject,
)
from app.services.audit import log_action

logger = logging.getLogger(__name__)

__all__ = [
    "GraphDeps",
    "StepError",
    "build_graph",
    "default_llm_factory",
    "run_graph",
]

LLMFactory = Callable[[Session, int], JsonLLM | None]
ReportFn = Callable[..., Any]

TOP_WEAK_SUBJECTS = 3
MAX_FALLBACKS_IN_SUMMARY = 20


class StepError(Exception):
    """A clear, user-facing reason for a failed step."""


class PartialStepError(Exception):
    """Soft failure: the step failed but produced output and the run may continue."""

    def __init__(self, message: str, output: dict[str, Any], updates: RunState) -> None:
        super().__init__(message)
        self.output = output
        self.updates = updates


def default_llm_factory(db: Session, school_id: int) -> JsonLLM | None:
    """Real OpenAI client when enabled and configured, else ``None`` (template mode)."""
    if not settings.llm_available:
        return None
    return LLMClient(db, school_id)


@dataclass
class GraphDeps:
    db: Session
    llm_factory: LLMFactory = default_llm_factory
    report_fn: ReportFn | None = None  # None -> app.reports.generator.generate_report
    today: Callable[[], date] = field(default=date.today)


def _now() -> datetime:
    return datetime.now(UTC)


def _j(value: Any) -> Any:
    return to_jsonable(value)


# ---------------------------------------------------------------------------
# Step bookkeeping
# ---------------------------------------------------------------------------


def _load_run(db: Session, run_id: int) -> AgentRun:
    run = db.get(AgentRun, run_id)
    if run is None:
        raise StepError(f"Agent run {run_id} not found")
    return run


def _execute_step(
    deps: GraphDeps,
    state: RunState,
    *,
    agent: str,
    action: str,
    input_summary: dict[str, Any],
    body: Callable[[AgentStep], tuple[dict[str, Any], RunState]],
    soft: bool = False,
) -> RunState:
    """Run ``body`` as one AgentStep, committing before and after (see module docstring)."""
    db = deps.db
    run_id = state["run_id"]
    school_id = state["school_id"]
    step = AgentStep(
        run_id=run_id,
        agent_name=agent,
        status=AgentStepStatus.running,
        started_at=_now(),
        input_summary=_j(input_summary),
    )
    db.add(step)
    db.commit()
    step_id = step.id
    logger.info("Run %s: %s started (step %s)", run_id, agent, step_id)

    try:
        output, updates = body(step)
    except PartialStepError as exc:
        if not soft:
            return _fail_step(deps, state, step_id, agent, str(exc))
        db.rollback()
        step = db.get(AgentStep, step_id) or step
        step.status = AgentStepStatus.failed
        step.finished_at = _now()
        step.output_summary = _j(exc.output)
        step.error = str(exc)
        warnings = [*state.get("warnings", []), f"{agent}: {exc}"]
        log_action(
            db,
            school_id=school_id,
            actor=agent,
            action=f"{action}_failed",
            entity_type="agent_run",
            entity_id=run_id,
            detail={"step_id": step_id, "status": "failed", "error": str(exc), "soft": True},
        )
        db.commit()
        logger.warning("Run %s: %s failed softly: %s", run_id, agent, exc)
        return {**exc.updates, "warnings": warnings}
    except (StepError, AppError) as exc:
        message = exc.message if isinstance(exc, AppError) else str(exc)
        return _fail_step(deps, state, step_id, agent, message)
    except Exception as exc:
        logger.exception("Run %s: %s crashed", run_id, agent)
        return _fail_step(deps, state, step_id, agent, f"{type(exc).__name__}: {exc}")

    step.status = AgentStepStatus.done
    step.finished_at = _now()
    step.output_summary = _j(output)
    log_action(
        db,
        school_id=school_id,
        actor=agent,
        action=action,
        entity_type="agent_run",
        entity_id=run_id,
        detail={"step_id": step_id, "status": "done", "summary": _j(output)},
    )
    db.commit()
    logger.info("Run %s: %s done", run_id, agent)
    return updates


def _fail_step(
    deps: GraphDeps, state: RunState, step_id: int, agent: str, message: str
) -> RunState:
    db = deps.db
    db.rollback()
    run_id = state["run_id"]
    step = db.get(AgentStep, step_id)
    if step is not None:
        step.status = AgentStepStatus.failed
        step.finished_at = _now()
        step.error = message
    run = db.get(AgentRun, run_id)
    if run is not None:
        run.status = AgentRunStatus.failed
        run.error = f"{agent}: {message}"
        run.finished_at = _now()
    log_action(
        db,
        school_id=state["school_id"],
        actor=agent,
        action="run_failed",
        entity_type="agent_run",
        entity_id=run_id,
        detail={"step_id": step_id, "error": message},
    )
    db.commit()
    logger.warning("Run %s failed at %s: %s", run_id, agent, message)
    return {"failed": True, "error": message}


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def _scope_label(section_ids: list[int] | None) -> str:
    return "selected classes" if section_ids else "all classes"


def data_quality_node(deps: GraphDeps, state: RunState) -> RunState:
    db = deps.db
    school_id = state["school_id"]
    exam_id = state["exam_id"]
    section_ids = state.get("class_section_ids") or None

    def body(_: AgentStep) -> tuple[dict[str, Any], RunState]:
        exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id))
        if exam is None:
            raise StepError("Exam not found")
        configs = db.execute(
            select(ExamSubjectConfig, Subject)
            .join(Subject, Subject.id == ExamSubjectConfig.subject_id)
            .where(ExamSubjectConfig.exam_id == exam.id, ExamSubjectConfig.school_id == school_id)
        ).all()
        mark_query = (
            select(Mark.subject_id, Mark.marks_obtained, Mark.is_absent, Student.class_section_id)
            .join(Student, Student.id == Mark.student_id)
            .where(Mark.exam_id == exam.id, Mark.school_id == school_id)
        )
        if section_ids:
            mark_query = mark_query.where(Student.class_section_id.in_(section_ids))
        rows = db.execute(mark_query).all()
        if not rows:
            raise StepError(
                f"No committed marks found for {exam.name} in {_scope_label(section_ids)}. "
                "Import and commit marks before running the analysis."
            )
        if not configs:
            raise StepError(
                f"No subjects are configured for {exam.name}. Configure the exam's subjects "
                "(max and pass marks) in Setup first."
            )

        configured = {cfg.subject_id: subj.name for cfg, subj in configs}
        sections = {r.class_section_id for r in rows}
        student_count = (
            db.scalar(
                select(func.count(Student.id)).where(
                    Student.school_id == school_id, Student.class_section_id.in_(sections)
                )
            )
            or 0
        )
        recorded = absent = blank = 0
        unconfigured: dict[int, int] = {}
        with_marks: set[int] = set()
        for r in rows:
            if r.subject_id not in configured:
                unconfigured[r.subject_id] = unconfigured.get(r.subject_id, 0) + 1
                continue
            with_marks.add(r.subject_id)
            if r.is_absent:
                absent += 1
            elif r.marks_obtained is None:
                blank += 1
            else:
                recorded += 1
        expected = student_count * len(configured)
        missing = max(0, expected - recorded - absent)

        issues: list[dict[str, Any]] = []
        warnings: list[str] = []
        if missing:
            msg = f"{missing} expected mark(s) are missing; they count as not passed."
            issues.append(
                {"code": dq.MISSING_MARK, "severity": "warning", "count": missing, "message": msg}
            )
            warnings.append(msg)
        if absent:
            msg = f"{absent} absence(s) recorded; absent papers count as not passed."
            issues.append(
                {"code": dq.ABSENT, "severity": "warning", "count": absent, "message": msg}
            )
            warnings.append(msg)
        unconfigured_names: list[str] = []
        if unconfigured:
            names = dict(
                db.execute(
                    select(Subject.id, Subject.name).where(Subject.id.in_(list(unconfigured)))
                ).all()
            )
            unconfigured_names = sorted(names.get(sid, f"#{sid}") for sid in unconfigured)
            msg = (
                f"Marks for {', '.join(unconfigured_names)} are ignored: the subject is not "
                f"configured for {exam.name}."
            )
            issues.append(
                {
                    "code": "UNCONFIGURED_SUBJECT",
                    "severity": "warning",
                    "count": sum(unconfigured.values()),
                    "message": msg,
                }
            )
            warnings.append(msg)
        no_marks = sorted(name for sid, name in configured.items() if sid not in with_marks)
        if no_marks:
            msg = f"No marks recorded for configured subject(s): {', '.join(no_marks)}."
            issues.append(
                {
                    "code": dq.MISSING_SUBJECT_COLUMN,
                    "severity": "warning",
                    "count": len(no_marks),
                    "message": msg,
                }
            )
            warnings.append(msg)

        completeness = round(100 * (recorded + absent) / expected, 1) if expected else 0.0
        output = {
            "exam": exam.name,
            "students": student_count,
            "class_sections": len(sections),
            "subjects_configured": len(configured),
            "marks_expected": expected,
            "marks_recorded": recorded,
            "absent": absent,
            "missing": missing,
            "blank_entries": blank,
            "completeness_pct": completeness,
            "unconfigured_subjects": unconfigured_names,
            "issues": issues,
            "warnings": warnings,
        }
        return output, {"quality": output, "warnings": [*state.get("warnings", []), *warnings]}

    return _execute_step(
        deps,
        state,
        agent=DATA_QUALITY,
        action="data_quality_checked",
        input_summary={"exam_id": exam_id, "class_section_ids": section_ids},
        body=body,
    )


def summarize_overview(overview: ExamOverview) -> dict[str, Any]:
    """Compact, JSON-safe analysis summary stored on the PerformanceAnalysis step."""
    s = overview.school_summary
    by_severity = {"high": 0, "medium": 0}
    by_reason: dict[str, int] = {}
    for a in overview.at_risk:
        by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
        for r in a.reasons:
            by_reason[r.code] = by_reason.get(r.code, 0) + 1

    def pass_key(sub: Any) -> tuple[Decimal, str]:
        pct = sub.overall.pass_percentage
        return (pct if pct is not None else Decimal(101), sub.subject_name)

    weak = sorted(overview.subject_summaries, key=pass_key)[:TOP_WEAK_SUBJECTS]
    return _j(
        {
            "exam": overview.exam.name,
            "previous_exam": overview.previous_exam.name if overview.previous_exam else None,
            "students": s.student_count,
            "appeared": s.appeared_count,
            "pass_count": s.pass_count,
            "pass_percentage": s.pass_percentage,
            "mean_percentage": s.mean_percentage,
            "median_percentage": s.median_percentage,
            "at_risk_total": len(overview.at_risk),
            "at_risk_by_severity": by_severity,
            "at_risk_by_reason": by_reason,
            "weakest_subjects": [
                {
                    "subject": sub.subject_name,
                    "pass_percentage": sub.overall.pass_percentage,
                    "mean_percentage": sub.overall.mean_percentage,
                    "change_points": sub.mean_percentage_change,
                }
                for sub in weak
            ],
            "classes": [
                {
                    "class": c.class_label,
                    "students": c.student_count,
                    "pass_percentage": c.pass_percentage,
                    "mean_percentage": c.mean_percentage,
                }
                for c in overview.class_summaries
            ],
        }
    )


def performance_analysis_node(deps: GraphDeps, state: RunState) -> RunState:
    section_ids = state.get("class_section_ids") or None

    def body(_: AgentStep) -> tuple[dict[str, Any], RunState]:
        overview = exam_overview(deps.db, state["school_id"], state["exam_id"], section_ids)
        summary = summarize_overview(overview)
        return summary, {"overview": overview, "analysis": summary}

    return _execute_step(
        deps,
        state,
        agent=PERFORMANCE_ANALYSIS,
        action="performance_analysed",
        input_summary={"exam_id": state["exam_id"], "class_section_ids": section_ids},
        body=body,
    )


def _existing_plan_students(db: Session, school_id: int, exam_id: int, ids: list[int]) -> set[int]:
    if not ids:
        return set()
    return set(
        db.scalars(
            select(InterventionPlan.student_id).where(
                InterventionPlan.school_id == school_id,
                InterventionPlan.student_id.in_(ids),
                InterventionPlan.status != InterventionStatus.rejected,
                InterventionPlan.evidence["exam_id"].as_integer() == exam_id,
            )
        )
    )


def intervention_drafting_node(deps: GraphDeps, state: RunState) -> RunState:
    db = deps.db
    school_id = state["school_id"]
    run_id = state["run_id"]

    def body(_: AgentStep) -> tuple[dict[str, Any], RunState]:
        overview: ExamOverview = state["overview"]
        exam = overview.exam
        results = {r.student_id: r for r in overview.results}
        at_risk_ids = [a.student_id for a in overview.at_risk]
        existing = _existing_plan_students(db, school_id, exam.id, at_risk_ids)
        todo = [a for a in overview.at_risk if a.student_id not in existing]
        cases = [iv.StudentCase.from_analysis(a, results.get(a.student_id)) for a in todo]

        population = list(results)
        pii_rows = (
            db.execute(
                select(Student.full_name, Student.admission_no).where(
                    Student.school_id == school_id, Student.id.in_(population)
                )
            ).all()
            if population
            else []
        )
        forbidden = forbidden_terms([r[0] for r in pii_rows], [r[1] for r in pii_rows])

        client: JsonLLM | None = None
        unavailable: str | None = None
        if cases:
            client = deps.llm_factory(db, school_id)
            if client is None:
                unavailable = "LLM disabled or not configured - deterministic templates used"
        context = iv.ExamContext(
            exam_name=exam.name,
            previous_exam_name=overview.previous_exam.name if overview.previous_exam else None,
        )
        outcome = iv.draft_plans(cases, context, client, forbidden, unavailable_reason=unavailable)

        today = deps.today()
        base = max(today, exam.held_on) if exam.held_on else today
        by_pseudo = {a.pseudo_id: a for a in todo}
        plan_ids: list[int] = []
        for case in cases:
            plan = outcome.plans[case.pseudo_id]
            mode = outcome.modes[case.pseudo_id]
            at = by_pseudo[case.pseudo_id]
            failed = case.failed_subjects
            evidence = _j(
                {
                    **at.to_dict(),
                    "exam_id": exam.id,
                    "exam_name": exam.name,
                    "previous_exam_name": context.previous_exam_name,
                    "run_id": run_id,
                    "subjects": [s.to_dict() for s in case.subjects],
                    "draft": {
                        "mode": mode,
                        "model": outcome.model if mode == "llm" else None,
                        "summary": plan.summary,
                        "focus_areas": plan.focus_areas,
                        "rationale": plan.rationale,
                        "reassess_after_weeks": plan.reassess_after_weeks,
                    },
                }
            )
            row = InterventionPlan(
                school_id=school_id,
                run_id=run_id,
                student_id=case.student_id,
                subject_id=failed[0].subject_id if len(failed) == 1 else None,
                status=InterventionStatus.draft,
                evidence=evidence,
                plan_text=iv.render_plan_text(plan),
                activities=[a.model_dump() for a in plan.activities],
                reassess_on=base + timedelta(weeks=plan.reassess_after_weeks),
            )
            db.add(row)
            db.flush()
            plan_ids.append(row.id)
            log_action(
                db,
                school_id=school_id,
                actor=INTERVENTION,
                action="plan_drafted",
                entity_type="intervention_plan",
                entity_id=row.id,
                detail={
                    "run_id": run_id,
                    "pseudo_id": case.pseudo_id,
                    "mode": mode,
                    "severity": case.severity,
                    "reasons": [r.code for r in case.reasons],
                },
            )

        run = _load_run(db, run_id)
        run.token_usage = (run.token_usage or 0) + outcome.tokens
        run.cost_usd = Decimal(run.cost_usd or 0) + outcome.cost_usd
        output = {
            "at_risk": len(overview.at_risk),
            "plans_created": len(plan_ids),
            "skipped_existing": len(existing),
            "mode": outcome.mode if cases else "none",
            "llm_plans": outcome.count("llm"),
            "template_plans": outcome.count("template"),
            "fallbacks": outcome.fallbacks[:MAX_FALLBACKS_IN_SUMMARY],
            "fallback_count": len(outcome.fallbacks),
            "llm_calls": outcome.llm_calls,
            "tokens": outcome.tokens,
            "cost_usd": str(outcome.cost_usd),
            "model": outcome.model,
            "note": outcome.note,
        }
        warnings = list(state.get("warnings", []))
        if outcome.fallbacks and client is not None:
            warnings.append(
                f"{len(outcome.fallbacks)} plan(s) used the template fallback "
                f"({outcome.note or 'invalid LLM output'})."
            )
        return output, {
            "plan_ids": plan_ids,
            "llm_mode": str(output["mode"]),
            "warnings": warnings,
        }

    return _execute_step(
        deps,
        state,
        agent=INTERVENTION,
        action="plans_drafted",
        input_summary={
            "exam_id": state["exam_id"],
            "at_risk": len(state["overview"].at_risk) if state.get("overview") else 0,
            "llm_enabled": settings.llm_available,
        },
        body=body,
    )


def reporting_node(deps: GraphDeps, state: RunState) -> RunState:
    db = deps.db

    def body(_: AgentStep) -> tuple[dict[str, Any], RunState]:
        from app.models import ReportFormat, ReportKind

        report_fn = deps.report_fn
        if report_fn is None:
            try:
                from app.reports.generator import generate_report
            except ImportError as exc:
                raise PartialStepError(
                    "Report generator is not available", {"reports": []}, {"report_ids": []}
                ) from exc
            report_fn = generate_report

        reports: list[dict[str, Any]] = []
        errors: list[str] = []
        for fmt in (ReportFormat.pdf, ReportFormat.xlsx):
            try:
                report = report_fn(
                    db,
                    school_id=state["school_id"],
                    kind=ReportKind.principal,
                    fmt=fmt,
                    exam_id=state["exam_id"],
                    class_section_id=None,
                    teacher_id=None,
                    run_id=state["run_id"],
                    created_by=state.get("requested_by"),
                )
                db.commit()
                reports.append({"id": report.id, "kind": "principal", "format": fmt.value})
            except Exception as exc:
                db.rollback()
                logger.warning("Run %s: %s report failed: %s", state["run_id"], fmt, exc)
                errors.append(f"{fmt.value.upper()} report failed: {exc}")
        ids = [r["id"] for r in reports]
        output = {"reports": reports, "errors": errors}
        if errors:
            raise PartialStepError("; ".join(errors), output, {"report_ids": ids})
        return output, {"report_ids": ids}

    return _execute_step(
        deps,
        state,
        agent=REPORTING,
        action="reports_generated",
        input_summary={
            "exam_id": state["exam_id"],
            "kind": "principal",
            "formats": ["pdf", "xlsx"],
        },
        body=body,
        soft=True,
    )


def finalize_node(deps: GraphDeps, state: RunState) -> RunState:
    db = deps.db
    run_id = state["run_id"]

    def body(_: AgentStep) -> tuple[dict[str, Any], RunState]:
        drafts = (
            db.scalar(
                select(func.count(InterventionPlan.id)).where(
                    InterventionPlan.run_id == run_id,
                    InterventionPlan.status == InterventionStatus.draft,
                )
            )
            or 0
        )
        run = _load_run(db, run_id)
        run.status = AgentRunStatus.awaiting_approval if drafts else AgentRunStatus.done
        run.finished_at = _now()
        output = {
            "status": run.status.value,
            "draft_plans": drafts,
            "reports": len(state.get("report_ids", [])),
            "llm_mode": state.get("llm_mode", "none"),
            "token_usage": run.token_usage,
            "cost_usd": str(run.cost_usd),
            "warnings": state.get("warnings", []),
        }
        return output, {}

    return _execute_step(
        deps,
        state,
        agent=ORCHESTRATOR,
        action="run_completed",
        input_summary={"plans": len(state.get("plan_ids", []))},
        body=body,
    )


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

NODES: tuple[tuple[str, Callable[[GraphDeps, RunState], RunState]], ...] = (
    ("data_quality", data_quality_node),
    ("performance_analysis", performance_analysis_node),
    ("intervention_drafting", intervention_drafting_node),
    ("reporting", reporting_node),
    ("finalize", finalize_node),
)


def build_graph(deps: GraphDeps) -> Any:
    """Compile the orchestrator graph bound to ``deps`` (one graph per run)."""
    graph = StateGraph(RunState)
    for name, fn in NODES:
        graph.add_node(name, lambda state, _fn=fn: _fn(deps, state))
    graph.add_edge(START, NODES[0][0])
    for (name, _), (nxt, _) in zip(NODES, NODES[1:], strict=False):
        graph.add_conditional_edges(
            name,
            lambda state, _nxt=nxt: END if state.get("failed") else _nxt,
            [nxt, END],
        )
    graph.add_edge(NODES[-1][0], END)
    return graph.compile()


def run_graph(
    db: Session,
    run_id: int,
    *,
    llm_factory: LLMFactory | None = None,
    report_fn: ReportFn | None = None,
    today: Callable[[], date] | None = None,
) -> AgentRun | None:
    """Execute a queued run synchronously on ``db``. Never raises for step failures."""
    run = db.get(AgentRun, run_id)
    if run is None:
        logger.error("Agent run %s not found", run_id)
        return None
    if run.status != AgentRunStatus.queued:
        logger.warning("Agent run %s is %s, not queued - skipping", run_id, run.status)
        return run
    params = run.input or {}
    run.status = AgentRunStatus.running
    log_action(
        db,
        school_id=run.school_id,
        actor=ORCHESTRATOR,
        action="run_started",
        entity_type="agent_run",
        entity_id=run.id,
        detail={"input": params},
    )
    db.commit()

    deps = GraphDeps(db=db)
    if llm_factory is not None:
        deps.llm_factory = llm_factory
    if report_fn is not None:
        deps.report_fn = report_fn
    if today is not None:
        deps.today = today

    initial: RunState = {
        "run_id": run.id,
        "school_id": run.school_id,
        "exam_id": int(params.get("exam_id", 0)),
        "class_section_ids": params.get("class_section_ids") or None,
        "requested_by": run.requested_by,
        "failed": False,
        "error": None,
        "warnings": [],
        "plan_ids": [],
        "report_ids": [],
    }
    try:
        build_graph(deps).invoke(initial)
    except Exception as exc:  # defensive: node wrappers already catch everything
        logger.exception("Agent run %s crashed", run_id)
        db.rollback()
        crashed = db.get(AgentRun, run_id)
        if crashed is not None and crashed.status in (
            AgentRunStatus.running,
            AgentRunStatus.queued,
        ):
            crashed.status = AgentRunStatus.failed
            crashed.error = f"Orchestrator: {type(exc).__name__}: {exc}"
            crashed.finished_at = _now()
            db.commit()
    db.refresh(run)
    return run
