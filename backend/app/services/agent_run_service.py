"""Read side of agent runs: list and detail (steps, plan counts, reports, warnings)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.state import INTERVENTION
from app.exceptions import NotFoundError
from app.models import AgentRun, AgentStep, AgentStepStatus, InterventionPlan, Report, User
from app.schemas.agent_runs import (
    AgentRunDetail,
    AgentRunList,
    AgentRunOut,
    AgentStepOut,
    RunReportOut,
)

logger = logging.getLogger(__name__)

MAX_LIST_LIMIT = 100


def get_run(db: Session, school_id: int, run_id: int) -> AgentRun:
    run = db.scalar(select(AgentRun).where(AgentRun.id == run_id, AgentRun.school_id == school_id))
    if run is None:
        raise NotFoundError("Agent run")
    return run


def _plan_counts(db: Session, run_ids: Sequence[int]) -> dict[int, dict[str, int]]:
    counts: dict[int, dict[str, int]] = {rid: {} for rid in run_ids}
    if not run_ids:
        return counts
    rows = db.execute(
        select(InterventionPlan.run_id, InterventionPlan.status, func.count(InterventionPlan.id))
        .where(InterventionPlan.run_id.in_(run_ids))
        .group_by(InterventionPlan.run_id, InterventionPlan.status)
    ).all()
    for run_id, status, n in rows:
        if run_id is not None:
            counts[run_id][status.value] = int(n)
    return counts


def _llm_modes(db: Session, run_ids: Sequence[int]) -> dict[int, str]:
    if not run_ids:
        return {}
    rows = db.execute(
        select(AgentStep.run_id, AgentStep.output_summary).where(
            AgentStep.run_id.in_(run_ids), AgentStep.agent_name == INTERVENTION
        )
    ).all()
    modes: dict[int, str] = {}
    for run_id, summary in rows:
        if isinstance(summary, dict) and summary.get("mode"):
            modes[run_id] = str(summary["mode"])
    return modes


def _emails(db: Session, user_ids: set[int | None]) -> dict[int, str]:
    ids = [u for u in user_ids if u is not None]
    if not ids:
        return {}
    return dict(db.execute(select(User.id, User.email).where(User.id.in_(ids))).all())


def _run_out(
    run: AgentRun,
    counts: dict[str, int],
    mode: str | None,
    emails: dict[int, str],
) -> dict[str, Any]:
    params = run.input or {}
    return {
        "id": run.id,
        "school_id": run.school_id,
        "kind": run.kind,
        "status": run.status,
        "requested_by": run.requested_by,
        "requested_by_email": emails.get(run.requested_by) if run.requested_by else None,
        "input": params,
        "exam_id": params.get("exam_id"),
        "exam_name": params.get("exam_name"),
        "created_at": run.created_at,
        "finished_at": run.finished_at,
        "token_usage": run.token_usage or 0,
        "cost_usd": run.cost_usd or 0,
        "error": run.error,
        "llm_mode": mode,
        "plan_counts": counts,
    }


def list_runs(db: Session, school_id: int, *, limit: int = 20, offset: int = 0) -> AgentRunList:
    limit = max(1, min(limit, MAX_LIST_LIMIT))
    total = db.scalar(select(func.count(AgentRun.id)).where(AgentRun.school_id == school_id)) or 0
    runs = db.scalars(
        select(AgentRun)
        .where(AgentRun.school_id == school_id)
        .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
        .limit(limit)
        .offset(max(0, offset))
    ).all()
    ids = [r.id for r in runs]
    counts = _plan_counts(db, ids)
    modes = _llm_modes(db, ids)
    emails = _emails(db, {r.requested_by for r in runs})
    return AgentRunList(
        items=[
            AgentRunOut.model_validate(_run_out(r, counts[r.id], modes.get(r.id), emails))
            for r in runs
        ],
        total=total,
    )


def _duration_ms(step: AgentStep) -> int | None:
    if step.started_at is None or step.finished_at is None:
        return None
    return max(0, int((step.finished_at - step.started_at).total_seconds() * 1000))


def run_detail(db: Session, school_id: int, run_id: int) -> AgentRunDetail:
    run = get_run(db, school_id, run_id)
    steps = db.scalars(
        select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.id)
    ).all()
    reports = db.scalars(
        select(Report)
        .where(Report.run_id == run.id, Report.school_id == school_id)
        .order_by(Report.id)
    ).all()
    counts = _plan_counts(db, [run.id])[run.id]
    modes = _llm_modes(db, [run.id])
    emails = _emails(db, {run.requested_by})

    warnings: list[str] = []
    for s in steps:
        summary = s.output_summary or {}
        if s.agent_name != "Orchestrator":
            for w in summary.get("warnings", []) or []:
                if isinstance(w, str) and w not in warnings:
                    warnings.append(w)
        if s.status == AgentStepStatus.failed and s.error and run.status.value != "failed":
            warnings.append(f"{s.agent_name}: {s.error}")

    step_out = [
        AgentStepOut.model_validate(
            {
                "id": s.id,
                "run_id": s.run_id,
                "agent_name": s.agent_name,
                "status": s.status,
                "started_at": s.started_at,
                "finished_at": s.finished_at,
                "duration_ms": _duration_ms(s),
                "input_summary": s.input_summary,
                "output_summary": s.output_summary,
                "error": s.error,
            }
        )
        for s in steps
    ]
    return AgentRunDetail.model_validate(
        {
            **_run_out(run, counts, modes.get(run.id), emails),
            "steps": step_out,
            "reports": [
                RunReportOut(
                    id=r.id, kind=r.kind.value, format=r.format.value, created_at=r.created_at
                )
                for r in reports
            ],
            "warnings": warnings,
        }
    )
