"""Pydantic schemas for /agent-runs (Module 5 orchestrator)."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models import AgentRunKind, AgentRunStatus, AgentStepStatus


class AgentRunCreate(BaseModel):
    exam_id: int = Field(gt=0)
    class_section_ids: list[int] | None = Field(default=None, max_length=200)


class AgentStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    agent_name: str
    status: AgentStepStatus
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None = None
    input_summary: dict[str, Any] | None
    output_summary: dict[str, Any] | None
    error: str | None


class RunReportOut(BaseModel):
    id: int
    kind: str
    format: str
    created_at: datetime


class AgentRunOut(BaseModel):
    id: int
    school_id: int
    kind: AgentRunKind
    status: AgentRunStatus
    requested_by: int | None
    requested_by_email: str | None = None
    input: dict[str, Any] | None
    exam_id: int | None = None
    exam_name: str | None = None
    created_at: datetime
    finished_at: datetime | None
    token_usage: int
    cost_usd: Decimal
    error: str | None
    llm_mode: str | None = None
    plan_counts: dict[str, int] = Field(default_factory=dict)


class AgentRunDetail(AgentRunOut):
    steps: list[AgentStepOut] = Field(default_factory=list)
    reports: list[RunReportOut] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AgentRunList(BaseModel):
    items: list[AgentRunOut]
    total: int
