"""Generated reports."""

import enum

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TenantMixin, TimestampMixin, str_enum


class ReportKind(enum.StrEnum):
    principal = "principal"
    class_teacher = "class_teacher"
    subject_teacher = "subject_teacher"


class ReportFormat(enum.StrEnum):
    pdf = "pdf"
    xlsx = "xlsx"


class Report(TenantMixin, TimestampMixin, Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="SET NULL"), index=True, nullable=True
    )
    kind: Mapped[ReportKind] = mapped_column(str_enum(ReportKind), nullable=False)
    format: Mapped[ReportFormat] = mapped_column(str_enum(ReportFormat), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
