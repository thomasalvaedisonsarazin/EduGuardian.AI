"""Shared state passed between the orchestrator graph's nodes (LangGraph ``StateGraph``)."""

from __future__ import annotations

from typing import Any, TypedDict

#: Agent names in execution order (also the AgentStep.agent_name values).
DATA_QUALITY = "DataQualityAgent"
PERFORMANCE_ANALYSIS = "PerformanceAnalysisAgent"
INTERVENTION = "InterventionAgent"
REPORTING = "ReportingAgent"
ORCHESTRATOR = "Orchestrator"

AGENT_ORDER: tuple[str, ...] = (
    DATA_QUALITY,
    PERFORMANCE_ANALYSIS,
    INTERVENTION,
    REPORTING,
    ORCHESTRATOR,
)


class RunState(TypedDict, total=False):
    """Graph state. Numbers come from deterministic code; nodes only add what they produced."""

    run_id: int
    school_id: int
    exam_id: int
    class_section_ids: list[int] | None
    requested_by: int | None

    failed: bool
    error: str | None
    warnings: list[str]

    quality: dict[str, Any]
    overview: Any  # app.analytics.service.ExamOverview - in-memory only, never persisted
    analysis: dict[str, Any]
    plan_ids: list[int]
    llm_mode: str
    report_ids: list[int]
