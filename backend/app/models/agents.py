"""Agent runs, steps, intervention plans and the audit log."""

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import JSONType, TenantMixin, TimestampMixin, str_enum

if TYPE_CHECKING:
    from app.models.academic import Student, Subject


class AgentRunKind(enum.StrEnum):
    full_analysis = "full_analysis"
    intervention_draft = "intervention_draft"
    report = "report"


class AgentRunStatus(enum.StrEnum):
    queued = "queued"
    running = "running"
    awaiting_approval = "awaiting_approval"
    done = "done"
    failed = "failed"


class AgentStepStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
    skipped = "skipped"


class InterventionStatus(enum.StrEnum):
    draft = "draft"
    approved = "approved"
    rejected = "rejected"
    in_progress = "in_progress"
    completed = "completed"


class AgentRun(TenantMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_school_id_created_at", "school_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[AgentRunKind] = mapped_column(str_enum(AgentRunKind), nullable=False)
    status: Mapped[AgentRunStatus] = mapped_column(
        str_enum(AgentRunStatus), default=AgentRunStatus.queued, nullable=False
    )
    requested_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    input: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_usage: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    steps: Mapped[list["AgentStep"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AgentStep.id",
    )
    interventions: Mapped[list["InterventionPlan"]] = relationship(back_populates="run")


class AgentStep(Base):
    """Child of AgentRun (tenant-scoped through its run; no school_id column)."""

    __tablename__ = "agent_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[AgentStepStatus] = mapped_column(
        str_enum(AgentStepStatus), default=AgentStepStatus.pending, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    output_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    run: Mapped["AgentRun"] = relationship(back_populates="steps")


class InterventionPlan(TenantMixin, TimestampMixin, Base):
    __tablename__ = "intervention_plans"
    __table_args__ = (Index("ix_intervention_plans_school_id_status", "school_id", "status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), index=True, nullable=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[InterventionStatus] = mapped_column(
        str_enum(InterventionStatus), default=InterventionStatus.draft, nullable=False
    )
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    plan_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    activities: Mapped[list[Any] | None] = mapped_column(JSONType, nullable=True)
    reassess_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped["AgentRun | None"] = relationship(back_populates="interventions")
    student: Mapped["Student"] = relationship()  # noqa: F821
    subject: Mapped["Subject | None"] = relationship()  # noqa: F821


class AuditLog(TenantMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_school_id_created_at", "school_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor: Mapped[str] = mapped_column(String(64), nullable=False)  # "user" or agent name
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
