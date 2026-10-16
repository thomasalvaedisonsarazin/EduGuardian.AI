"""All ORM models and enums. Importing this package registers every table on Base.metadata."""

from app.database import Base
from app.models.academic import (
    AcademicYear,
    ClassSection,
    Exam,
    ExamSubjectConfig,
    Student,
    Subject,
    Teacher,
    TeachingAssignment,
)
from app.models.agents import (
    AgentRun,
    AgentRunKind,
    AgentRunStatus,
    AgentStep,
    AgentStepStatus,
    AuditLog,
    InterventionPlan,
    InterventionStatus,
)
from app.models.base import SoftDeleteMixin, TenantMixin, TimestampMixin
from app.models.marks import ImportBatch, ImportStatus, Mark
from app.models.reports import Report, ReportFormat, ReportKind
from app.models.tenancy import Membership, MembershipRole, RefreshToken, School, User

__all__ = [
    "Base",
    "TimestampMixin",
    "TenantMixin",
    "SoftDeleteMixin",
    # tenancy
    "School",
    "User",
    "Membership",
    "MembershipRole",
    "RefreshToken",
    # academic
    "AcademicYear",
    "ClassSection",
    "Subject",
    "Teacher",
    "TeachingAssignment",
    "Student",
    "Exam",
    "ExamSubjectConfig",
    # marks
    "Mark",
    "ImportBatch",
    "ImportStatus",
    # agents
    "AgentRun",
    "AgentRunKind",
    "AgentRunStatus",
    "AgentStep",
    "AgentStepStatus",
    "InterventionPlan",
    "InterventionStatus",
    "AuditLog",
    # reports
    "Report",
    "ReportKind",
    "ReportFormat",
]
