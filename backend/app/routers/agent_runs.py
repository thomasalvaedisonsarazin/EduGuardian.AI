"""Agent run endpoints (Module 5): start the orchestrated analysis and poll its progress."""

import logging
from collections.abc import Callable

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session

from app.agents.orchestrator import execute_run, start_run
from app.dependencies import TenantContext, get_db, require_roles
from app.models import MembershipRole
from app.schemas.agent_runs import AgentRunCreate, AgentRunDetail, AgentRunList
from app.services import agent_run_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])

_member = require_roles()
_runner = require_roles(
    MembershipRole.school_admin, MembershipRole.principal, MembershipRole.coordinator
)

RunExecutor = Callable[[int], None]


def get_run_executor() -> RunExecutor:
    """Background executor for queued runs (overridable in tests)."""
    return execute_run


@router.post("", response_model=AgentRunDetail, status_code=202)
def create_run(
    body: AgentRunCreate,
    background_tasks: BackgroundTasks,
    ctx: TenantContext = Depends(_runner),
    db: Session = Depends(get_db),
    executor: RunExecutor = Depends(get_run_executor),
) -> AgentRunDetail:
    """Queue a full analysis run for an exam; it executes in the background."""
    run = start_run(db, ctx, body.exam_id, body.class_section_ids)
    background_tasks.add_task(executor, run.id)
    return agent_run_service.run_detail(db, ctx.school_id, run.id)


@router.get("", response_model=AgentRunList)
def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ctx: TenantContext = Depends(_member),
    db: Session = Depends(get_db),
) -> AgentRunList:
    """Runs of the active school, newest first."""
    return agent_run_service.list_runs(db, ctx.school_id, limit=limit, offset=offset)


@router.get("/{run_id}", response_model=AgentRunDetail)
def get_run(
    run_id: int, ctx: TenantContext = Depends(_member), db: Session = Depends(get_db)
) -> AgentRunDetail:
    """Run with its ordered steps, plan counts by status, reports and warnings (poll this)."""
    return agent_run_service.run_detail(db, ctx.school_id, run_id)
