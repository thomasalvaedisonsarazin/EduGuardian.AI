"""Orchestrator entry points: create a queued run, then execute it in the background.

``start_run`` validates the request (tenant-scoped) and stores an ``AgentRun(queued)``.
``execute_run`` is what FastAPI ``BackgroundTasks`` calls: it opens its own session (the
request's session is closed by then) and runs the LangGraph orchestrator.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.graph import run_graph
from app.agents.state import ORCHESTRATOR
from app.analytics.loader import get_exam
from app.dependencies import TenantContext
from app.exceptions import ConflictError, NotFoundError
from app.models import AgentRun, AgentRunKind, AgentRunStatus, ClassSection
from app.services.audit import log_action

logger = logging.getLogger(__name__)

__all__ = ["ACTIVE_RUN_WINDOW", "execute_run", "start_run"]

#: A queued/running run younger than this blocks a duplicate run for the same exam.
ACTIVE_RUN_WINDOW = timedelta(minutes=15)


def start_run(
    db: Session,
    ctx: TenantContext,
    exam_id: int,
    class_section_ids: list[int] | None = None,
) -> AgentRun:
    """Create (and commit) a queued full-analysis run for ``exam_id``."""
    exam = get_exam(db, ctx.school_id, exam_id)  # 404 for foreign exams
    section_ids = sorted(set(class_section_ids)) if class_section_ids else None
    if section_ids:
        found = set(
            db.scalars(
                select(ClassSection.id).where(
                    ClassSection.id.in_(section_ids), ClassSection.school_id == ctx.school_id
                )
            )
        )
        if found != set(section_ids):
            raise NotFoundError("Class section")

    cutoff = datetime.now(UTC) - ACTIVE_RUN_WINDOW
    active = db.scalars(
        select(AgentRun).where(
            AgentRun.school_id == ctx.school_id,
            AgentRun.status.in_([AgentRunStatus.queued, AgentRunStatus.running]),
            AgentRun.created_at >= cutoff,
        )
    ).all()
    if any((r.input or {}).get("exam_id") == exam.id for r in active):
        raise ConflictError("An analysis run for this exam is already in progress")

    run = AgentRun(
        school_id=ctx.school_id,
        kind=AgentRunKind.full_analysis,
        status=AgentRunStatus.queued,
        requested_by=ctx.user.id,
        input={"exam_id": exam.id, "exam_name": exam.name, "class_section_ids": section_ids},
        token_usage=0,
        cost_usd=0,
    )
    db.add(run)
    db.flush()
    log_action(
        db,
        school_id=ctx.school_id,
        actor="user",
        user_id=ctx.user.id,
        action="run_requested",
        entity_type="agent_run",
        entity_id=run.id,
        detail={"exam_id": exam.id, "exam_name": exam.name, "class_section_ids": section_ids},
    )
    db.commit()
    logger.info("Queued agent run %s (school=%s exam=%s)", run.id, ctx.school_id, exam.id)
    return run


def execute_run(run_id: int, session_factory: Callable[[], Session] | None = None) -> None:
    """Run the orchestrator graph for ``run_id`` in a fresh session (background task)."""
    if session_factory is None:
        from app.database import SessionLocal

        session_factory = SessionLocal
    db = session_factory()
    try:
        run_graph(db, run_id)
    except Exception:
        logger.exception("Background execution of run %s failed", run_id)
        db.rollback()
        run = db.get(AgentRun, run_id)
        if run is not None and run.status in (AgentRunStatus.queued, AgentRunStatus.running):
            run.status = AgentRunStatus.failed
            run.error = f"{ORCHESTRATOR}: unexpected error"
            run.finished_at = datetime.now(UTC)
            db.commit()
    finally:
        db.close()
