"""Academic setup models."""

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TenantMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.marks import Mark


class AcademicYear(TenantMixin, TimestampMixin, Base):
    __tablename__ = "academic_years"
    __table_args__ = (UniqueConstraint("school_id", "label"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "2026-27"
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    class_sections: Mapped[list["ClassSection"]] = relationship(back_populates="academic_year")
    exams: Mapped[list["Exam"]] = relationship(back_populates="academic_year")


class ClassSection(TenantMixin, TimestampMixin, Base):
    __tablename__ = "class_sections"
    __table_args__ = (UniqueConstraint("school_id", "academic_year_id", "grade", "section"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"), index=True, nullable=False
    )
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(10), nullable=False)

    academic_year: Mapped["AcademicYear"] = relationship(back_populates="class_sections")
    students: Mapped[list["Student"]] = relationship(back_populates="class_section")
    teaching_assignments: Mapped[list["TeachingAssignment"]] = relationship(
        back_populates="class_section"
    )


class Subject(TenantMixin, TimestampMixin, Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("school_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)


class Teacher(TenantMixin, TimestampMixin, Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)

    teaching_assignments: Mapped[list["TeachingAssignment"]] = relationship(
        back_populates="teacher", cascade="all, delete-orphan", passive_deletes=True
    )


class TeachingAssignment(TenantMixin, TimestampMixin, Base):
    __tablename__ = "teaching_assignments"
    __table_args__ = (UniqueConstraint("teacher_id", "class_section_id", "subject_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teachers.id", ondelete="CASCADE"), index=True, nullable=False
    )
    class_section_id: Mapped[int] = mapped_column(
        ForeignKey("class_sections.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    is_class_teacher: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    teacher: Mapped["Teacher"] = relationship(back_populates="teaching_assignments")
    class_section: Mapped["ClassSection"] = relationship(back_populates="teaching_assignments")
    subject: Mapped["Subject"] = relationship()


class Student(TenantMixin, TimestampMixin, Base):
    __tablename__ = "students"
    __table_args__ = (
        UniqueConstraint("school_id", "admission_no"),
        UniqueConstraint("school_id", "pseudo_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    class_section_id: Mapped[int] = mapped_column(
        ForeignKey("class_sections.id", ondelete="CASCADE"), index=True, nullable=False
    )
    admission_no: Mapped[str] = mapped_column(String(50), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    pseudo_id: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "S-0042"

    class_section: Mapped["ClassSection"] = relationship(back_populates="students")
    marks: Mapped[list["Mark"]] = relationship(  # noqa: F821
        back_populates="student", cascade="all, delete-orphan", passive_deletes=True
    )


class Exam(TenantMixin, TimestampMixin, Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(primary_key=True)
    academic_year_id: Mapped[int] = mapped_column(
        ForeignKey("academic_years.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    held_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    academic_year: Mapped["AcademicYear"] = relationship(back_populates="exams")
    subject_configs: Mapped[list["ExamSubjectConfig"]] = relationship(
        back_populates="exam", cascade="all, delete-orphan", passive_deletes=True
    )


class ExamSubjectConfig(TenantMixin, TimestampMixin, Base):
    __tablename__ = "exam_subject_configs"
    __table_args__ = (UniqueConstraint("exam_id", "subject_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"), index=True, nullable=False
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    max_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    pass_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)

    exam: Mapped["Exam"] = relationship(back_populates="subject_configs")
    subject: Mapped["Subject"] = relationship()
