"""Intervention plans: review queue, edits and the human-in-the-loop approval workflow.

Status machine::

    draft --approve--> approved --start--> in_progress --complete--> completed
    draft --reject---> rejected

Who may review (edit / approve / reject / change status):
* school_admin, principal, coordinator: any plan of the school;
* teacher: plans of students in class sections they teach (TeachingAssignment through
  ``Teacher.user_id``). Teachers also only *see* those plans.

Every change writes an AuditLog entry (actor ``"user"``). When the last draft of a run is
decided the run moves from ``awaiting_approval`` to ``done``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.agents.state import ORCHESTRATOR
from app.analytics.loader import class_label
from app.dependencies import TenantContext
from app.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models import (
    AgentRun,
    AgentRunStatus,
    ClassSection,
    InterventionPlan,
    InterventionStatus,
    MembershipRole,
    Student,
    Subject,
    Teacher,
    TeachingAssignment,
    User,
)
from app.schemas.interventions import (
    InterventionList,
    InterventionOut,
    InterventionUpdate,
    RejectRequest,
    StatusUpdate,
    StudentRef,
)
from app.services.audit import log_action

logger = logging.getLogger(__name__)

REVIEWER_ROLES = frozenset(
    {MembershipRole.school_admin, MembershipRole.principal, MembershipRole.coordinator}
)
MAX_LIMIT = 200

#: Allowed PATCH /status transitions.
STATUS_TRANSITIONS: dict[InterventionStatus, InterventionStatus] = {
    InterventionStatus.in_progress: InterventionStatus.approved,
    InterventionStatus.completed: InterventionStatus.in_progress,
}


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------


def _is_reviewer(ctx: TenantContext) -> bool:
    return ctx.role in REVIEWER_ROLES or bool(getattr(ctx.user, "is_superadmin", False))


def taught_section_ids(db: Session, ctx: TenantContext) -> set[int]:
    """Class sections the caller teaches in the active school (via Teacher.user_id)."""
    return set(
        db.scalars(
            select(TeachingAssignment.class_section_id)
            .join(Teacher, Teacher.id == TeachingAssignment.teacher_id)
            .where(
                Teacher.user_id == ctx.user.id,
                Teacher.school_id == ctx.school_id,
                TeachingAssignment.school_id == ctx.school_id,
            )
        )
    )


def can_review(db: Session, ctx: TenantContext, student: Student) -> bool:
    if _is_reviewer(ctx):
        return True
    return student.class_section_id in taught_section_ids(db, ctx)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def _scoped_query(
    db: Session, ctx: TenantContext
) -> Select[InterventionPlan, Student, ClassSection]:
    query = (
        select(InterventionPlan, Student, ClassSection)
        .join(Student, Student.id == InterventionPlan.student_id)
        .join(ClassSection, ClassSection.id == Student.class_section_id)
        .where(InterventionPlan.school_id == ctx.school_id)
    )
    if not _is_reviewer(ctx):
        query = query.where(Student.class_section_id.in_(taught_section_ids(db, ctx) or {-1}))
    return query


def _get_row(
    db: Session, ctx: TenantContext, plan_id: int
) -> tuple[InterventionPlan, Student, ClassSection]:
    # Tenant-scoped only (foreign -> 404); role checks happen in the callers (-> 403).
    row = db.execute(
        select(InterventionPlan, Student, ClassSection)
        .join(Student, Student.id == InterventionPlan.student_id)
        .join(ClassSection, ClassSection.id == Student.class_section_id)
        .where(InterventionPlan.school_id == ctx.school_id, InterventionPlan.id == plan_id)
    ).first()
    if row is None:
        raise NotFoundError("Intervention plan")
    return row[0], row[1], row[2]


def _to_out(
    db: Session,
    plan: InterventionPlan,
    student: Student,
    section: ClassSection,
    *,
    reviewer: bool,
    taught: set[int],
    subjects: dict[int, str] | None = None,
    emails: dict[int, str] | None = None,
) -> InterventionOut:
    evidence = plan.evidence or {}
    subject_name: str | None = None
    if plan.subject_id is not None:
        if subjects is not None:
            subject_name = subjects.get(plan.subject_id)
        else:
            subject = db.get(Subject, plan.subject_id)
            subject_name = subject.name if subject else None
    approved_email: str | None = None
    if plan.approved_by is not None:
        if emails is not None:
            approved_email = emails.get(plan.approved_by)
        else:
            user = db.get(User, plan.approved_by)
            approved_email = user.email if user else None
    exam_id = evidence.get("exam_id")
    return InterventionOut(
        id=plan.id,
        run_id=plan.run_id,
        student=StudentRef(
            id=student.id,
            full_name=student.full_name,
            pseudo_id=student.pseudo_id,
            admission_no=student.admission_no,
            class_section_id=section.id,
            class_label=class_label(section),
        ),
        subject_id=plan.subject_id,
        subject_name=subject_name,
        status=plan.status,
        severity=evidence.get("severity"),
        exam_id=int(exam_id) if isinstance(exam_id, int | str) and str(exam_id).isdigit() else None,
        exam_name=evidence.get("exam_name"),
        evidence=evidence,
        plan_text=plan.plan_text,
        activities=[a for a in (plan.activities or []) if isinstance(a, dict)],
        reassess_on=plan.reassess_on,
        approved_by=plan.approved_by,
        approved_by_email=approved_email,
        approved_at=plan.approved_at,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        can_review=reviewer or section.id in taught,
    )


def list_plans(
    db: Session,
    ctx: TenantContext,
    *,
    status: InterventionStatus | None = None,
    class_section_id: int | None = None,
    exam_id: int | None = None,
    run_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> InterventionList:
    base = _scoped_query(db, ctx)
    if class_section_id is not None:
        base = base.where(Student.class_section_id == class_section_id)
    if exam_id is not None:
        base = base.where(InterventionPlan.evidence["exam_id"].as_integer() == exam_id)
    if run_id is not None:
        base = base.where(InterventionPlan.run_id == run_id)

    # counts by status (for the tabs) use every filter except status
    status_sub = base.with_only_columns(InterventionPlan.status).subquery()
    count_rows = db.execute(
        select(status_sub.c.status, func.count()).group_by(status_sub.c.status)
    ).all()
    counts = {s.value: 0 for s in InterventionStatus}
    for st, n in count_rows:
        key = st.value if isinstance(st, InterventionStatus) else str(st)
        counts[key] = int(n)

    query = base
    if status is not None:
        query = query.where(InterventionPlan.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(
        query.order_by(InterventionPlan.created_at.desc(), InterventionPlan.id.desc())
        .limit(max(1, min(limit, MAX_LIMIT)))
        .offset(max(0, offset))
    ).all()

    reviewer = _is_reviewer(ctx)
    taught = set() if reviewer else taught_section_ids(db, ctx)
    subject_ids = {p.subject_id for p, _, _ in rows if p.subject_id is not None}
    subjects = (
        dict(db.execute(select(Subject.id, Subject.name).where(Subject.id.in_(subject_ids))).all())
        if subject_ids
        else {}
    )
    user_ids = {p.approved_by for p, _, _ in rows if p.approved_by is not None}
    emails = (
        dict(db.execute(select(User.id, User.email).where(User.id.in_(user_ids))).all())
        if user_ids
        else {}
    )
    items = [
        _to_out(db, p, s, c, reviewer=reviewer, taught=taught, subjects=subjects, emails=emails)
        for p, s, c in rows
    ]
    return InterventionList(items=items, total=total, counts=counts)


def get_plan(db: Session, ctx: TenantContext, plan_id: int) -> InterventionOut:
    plan, student, section = _get_row(db, ctx, plan_id)
    if not can_review(db, ctx, student):
        raise ForbiddenError("You can only view plans for students in classes you teach")
    reviewer = _is_reviewer(ctx)
    taught = set() if reviewer else taught_section_ids(db, ctx)
    return _to_out(db, plan, student, section, reviewer=reviewer, taught=taught)


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------


def _reviewable(
    db: Session, ctx: TenantContext, plan_id: int
) -> tuple[InterventionPlan, Student, ClassSection]:
    plan, student, section = _get_row(db, ctx, plan_id)
    if not can_review(db, ctx, student):
        raise ForbiddenError("You can only review plans for students in classes you teach")
    return plan, student, section


def _require_status(plan: InterventionPlan, *allowed: InterventionStatus) -> None:
    if plan.status not in allowed:
        names = ", ".join(s.value for s in allowed)
        raise ConflictError(
            f"Plan is {plan.status.value}; this action requires status {names}",
            code="INVALID_STATUS",
        )


def _close_run_if_decided(db: Session, plan: InterventionPlan) -> None:
    if plan.run_id is None:
        return
    run = db.get(AgentRun, plan.run_id)
    if run is None or run.status != AgentRunStatus.awaiting_approval:
        return
    remaining = (
        db.scalar(
            select(func.count(InterventionPlan.id)).where(
                InterventionPlan.run_id == run.id,
                InterventionPlan.status == InterventionStatus.draft,
            )
        )
        or 0
    )
    if remaining == 0:
        run.status = AgentRunStatus.done
        log_action(
            db,
            school_id=run.school_id,
            actor=ORCHESTRATOR,
            action="run_closed",
            entity_type="agent_run",
            entity_id=run.id,
            detail={"reason": "all draft plans reviewed"},
        )
        logger.info("Run %s closed: all plans reviewed", run.id)


def _finish(
    db: Session, ctx: TenantContext, plan: InterventionPlan, student: Student, section: ClassSection
) -> InterventionOut:
    db.commit()
    db.refresh(plan)
    return _to_out(db, plan, student, section, reviewer=_is_reviewer(ctx), taught={section.id})


def update_plan(
    db: Session, ctx: TenantContext, plan_id: int, body: InterventionUpdate
) -> InterventionOut:
    plan, student, section = _reviewable(db, ctx, plan_id)
    _require_status(plan, InterventionStatus.draft)
    changed: list[str] = []
    if body.plan_text is not None and body.plan_text != plan.plan_text:
        plan.plan_text = body.plan_text
        changed.append("plan_text")
    if body.activities is not None:
        plan.activities = [a.model_dump() for a in body.activities]
        changed.append("activities")
    if "reassess_on" in body.model_fields_set and body.reassess_on != plan.reassess_on:
        plan.reassess_on = body.reassess_on
        changed.append("reassess_on")
    if changed:
        log_action(
            db,
            school_id=ctx.school_id,
            actor="user",
            user_id=ctx.user.id,
            action="plan_edited",
            entity_type="intervention_plan",
            entity_id=plan.id,
            detail={"fields": changed, "pseudo_id": student.pseudo_id},
        )
    return _finish(db, ctx, plan, student, section)


def approve_plan(db: Session, ctx: TenantContext, plan_id: int) -> InterventionOut:
    plan, student, section = _reviewable(db, ctx, plan_id)
    _require_status(plan, InterventionStatus.draft)
    plan.status = InterventionStatus.approved
    plan.approved_by = ctx.user.id
    plan.approved_at = datetime.now(UTC)
    log_action(
        db,
        school_id=ctx.school_id,
        actor="user",
        user_id=ctx.user.id,
        action="plan_approved",
        entity_type="intervention_plan",
        entity_id=plan.id,
        detail={"pseudo_id": student.pseudo_id, "run_id": plan.run_id, "role": ctx.role.value},
    )
    db.flush()
    _close_run_if_decided(db, plan)
    return _finish(db, ctx, plan, student, section)


def reject_plan(
    db: Session, ctx: TenantContext, plan_id: int, body: RejectRequest
) -> InterventionOut:
    plan, student, section = _reviewable(db, ctx, plan_id)
    _require_status(plan, InterventionStatus.draft)
    plan.status = InterventionStatus.rejected
    reason = (body.reason or "").strip() or None
    evidence = dict(plan.evidence or {})
    evidence["rejection"] = {
        "reason": reason,
        "by": ctx.user.id,
        "at": datetime.now(UTC).isoformat(),
    }
    plan.evidence = evidence
    log_action(
        db,
        school_id=ctx.school_id,
        actor="user",
        user_id=ctx.user.id,
        action="plan_rejected",
        entity_type="intervention_plan",
        entity_id=plan.id,
        detail={"pseudo_id": student.pseudo_id, "run_id": plan.run_id, "reason": reason},
    )
    db.flush()
    _close_run_if_decided(db, plan)
    return _finish(db, ctx, plan, student, section)


def change_status(
    db: Session, ctx: TenantContext, plan_id: int, body: StatusUpdate
) -> InterventionOut:
    plan, student, section = _reviewable(db, ctx, plan_id)
    target = InterventionStatus(body.status)
    _require_status(plan, STATUS_TRANSITIONS[target])
    previous = plan.status
    plan.status = target
    log_action(
        db,
        school_id=ctx.school_id,
        actor="user",
        user_id=ctx.user.id,
        action="plan_status_changed",
        entity_type="intervention_plan",
        entity_id=plan.id,
        detail={
            "pseudo_id": student.pseudo_id,
            "from": previous.value,
            "to": target.value,
            "note": body.note,
        },
    )
    return _finish(db, ctx, plan, student, section)
