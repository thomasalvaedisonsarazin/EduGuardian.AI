"""Marks and import batches."""

import enum
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import JSONType, TenantMixin, TimestampMixin, str_enum

if TYPE_CHECKING:
    from app.models.academic import Exam, Student, Subject


class ImportStatus(enum.StrEnum):
    uploaded = "uploaded"
    validated = "validated"
    committed = "committed"
    rejected = "rejected"


class Mark(TenantMixin, TimestampMixin, Base):
    __tablename__ = "marks"
    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", "subject_id"),
        Index("ix_marks_school_id_exam_id", "school_id", "exam_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"), index=True, nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    marks_obtained: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    is_absent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    exam: Mapped["Exam"] = relationship()  # noqa: F821
    student: Mapped["Student"] = relationship(back_populates="marks")  # noqa: F821
    subject: Mapped["Subject"] = relationship()  # noqa: F821


class ImportBatch(TenantMixin, TimestampMixin, Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"), index=True, nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ImportStatus] = mapped_column(
        str_enum(ImportStatus), default=ImportStatus.uploaded, nullable=False
    )
    column_map: Mapped[dict[str, Any] | None] = mapped_column(JSONType, nullable=True)
    issues: Mapped[list[Any] | None] = mapped_column(JSONType, nullable=True)
    preview: Mapped[list[Any] | None] = mapped_column(JSONType, nullable=True)  # parsed rows
    uploaded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    exam: Mapped["Exam"] = relationship()  # noqa: F821
