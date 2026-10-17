"""API tests for /agent-runs, /interventions and /audit-logs (roles, tenancy, audit trail)."""

from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.graph import run_graph
from app.dependencies import TenantContext
from app.main import app
from app.models import (
    AgentRun,
    AuditLog,
    ClassSection,
    Exam,
    InterventionPlan,
    MembershipRole,
    School,
    Student,
    Subject,
    Teacher,
    TeachingAssignment,
)
from app.routers.agent_runs import get_run_executor
from app.seed.demo import seed_demo

ClientAs = Callable[[TenantContext], TestClient]
MakeTenant = Callable[..., TenantContext]


@pytest.fixture()
def school(db: Session) -> School:
    summary = seed_demo(db, sample_dir=None, commit=False)
    found = db.get(School, summary.school_id)
    assert found is not None
    return found


@pytest.fixture()
def exam(db: Session, school: School) -> Exam:
    found = db.scalar(select(Exam).where(Exam.school_id == school.id, Exam.sequence == 2))
    assert found is not None
    return found


@pytest.fixture()
def sync_executor(db: Session) -> Any:
    """Run queued runs synchronously on the test session (template mode, no reports)."""

    def executor(run_id: int) -> None:
        run_graph(
            db,
            run_id,
            llm_factory=lambda _db, _sid: None,
            report_fn=_no_report,
            today=lambda: date(2026, 10, 16),
        )

    app.dependency_overrides[get_run_executor] = lambda: executor
    yield executor
    app.dependency_overrides.pop(get_run_executor, None)


def _no_report(_db: Session, **_: Any) -> Any:
    raise RuntimeError("reports disabled in this test")


def start(client: TestClient, exam: Exam) -> dict[str, Any]:
    resp = client.post("/api/v1/agent-runs", json={"exam_id": exam.id})
    assert resp.status_code == 202, resp.text
    return resp.json()


def teacher_for_section(
    db: Session, make_tenant: MakeTenant, school: School, section_id: int
) -> TenantContext:
    ctx = make_tenant(MembershipRole.teacher, school=school)
    teacher = Teacher(school_id=school.id, user_id=ctx.user.id, full_name="Section Teacher")
    db.add(teacher)
    db.flush()
    subject = db.scalar(select(Subject).where(Subject.school_id == school.id))
    assert subject is not None
    db.add(
        TeachingAssignment(
            school_id=school.id,
            teacher_id=teacher.id,
            class_section_id=section_id,
            subject_id=subject.id,
        )
    )
    db.flush()
    return ctx


# --- agent runs ----------------------------------------------------------------------------


def test_start_run_and_poll(
    db: Session,
    school: School,
    exam: Exam,
    make_tenant: MakeTenant,
    client_as: ClientAs,
    sync_executor: Any,
) -> None:
    admin = make_tenant(MembershipRole.principal, school=school)
    client = client_as(admin)
    created = start(client, exam)
    assert created["status"] == "queued" and created["exam_id"] == exam.id

    detail = client.get(f"/api/v1/agent-runs/{created['id']}").json()
    assert detail["status"] == "awaiting_approval"
    assert [s["agent_name"] for s in detail["steps"]] == [
        "DataQualityAgent",
        "PerformanceAnalysisAgent",
        "InterventionAgent",
        "ReportingAgent",
        "Orchestrator",
    ]
    assert detail["steps"][0]["duration_ms"] is not None
    assert detail["plan_counts"]["draft"] > 0
    assert detail["llm_mode"] == "template"
    assert any("ReportingAgent" in w for w in detail["warnings"])

    listing = client.get("/api/v1/agent-runs").json()
    assert listing["total"] == 1 and listing["items"][0]["id"] == created["id"]


def test_start_run_validation_and_roles(
    db: Session,
    school: School,
    exam: Exam,
    make_tenant: MakeTenant,
    client_as: ClientAs,
    sync_executor: Any,
) -> None:
    teacher = make_tenant(MembershipRole.teacher, school=school)
    assert (
        client_as(teacher).post("/api/v1/agent-runs", json={"exam_id": exam.id}).status_code == 403
    )

    admin = client_as(make_tenant(MembershipRole.school_admin, school=school))
    assert admin.post("/api/v1/agent-runs", json={"exam_id": 999999}).status_code == 404
    bad_section = admin.post(
        "/api/v1/agent-runs", json={"exam_id": exam.id, "class_section_ids": [999999]}
    )
    assert bad_section.status_code == 404


def test_duplicate_active_run_conflicts(
    db: Session, school: School, exam: Exam, make_tenant: MakeTenant, client_as: ClientAs
) -> None:
    app.dependency_overrides[get_run_executor] = lambda: lambda _run_id: None
    try:
        client = client_as(make_tenant(MembershipRole.coordinator, school=school))
        start(client, exam)
        assert client.post("/api/v1/agent-runs", json={"exam_id": exam.id}).status_code == 409
    finally:
        app.dependency_overrides.pop(get_run_executor, None)


def test_agent_runs_cross_tenant_404(
    db: Session,
    school: School,
    exam: Exam,
    make_tenant: MakeTenant,
    client_as: ClientAs,
    sync_executor: Any,
) -> None:
    run = start(client_as(make_tenant(MembershipRole.school_admin, school=school)), exam)
    other = client_as(make_tenant(MembershipRole.school_admin))
    assert other.get(f"/api/v1/agent-runs/{run['id']}").status_code == 404
    assert other.get("/api/v1/agent-runs").json()["total"] == 0
    assert other.post("/api/v1/agent-runs", json={"exam_id": exam.id}).status_code == 404
    assert other.get("/api/v1/interventions").json()["total"] == 0


# --- interventions -------------------------------------------------------------------------


def test_review_queue_edit_approve_reject_and_close_run(
    db: Session,
    school: School,
    exam: Exam,
    make_tenant: MakeTenant,
    client_as: ClientAs,
    sync_executor: Any,
) -> None:
    admin_ctx = make_tenant(MembershipRole.school_admin, school=school)
    client = client_as(admin_ctx)
    run = start(client, exam)

    queue = client.get("/api/v1/interventions", params={"run_id": run["id"], "status": "draft"})
    body = queue.json()
    assert body["total"] == body["counts"]["draft"] > 1
    first = body["items"][0]
    assert first["student"]["full_name"] and first["exam_id"] == exam.id
    assert first["evidence"]["reasons"] and first["can_review"] is True

    by_exam = client.get("/api/v1/interventions", params={"exam_id": exam.id}).json()
    assert by_exam["total"] == body["total"]
    section_id = first["student"]["class_section_id"]
    by_class = client.get("/api/v1/interventions", params={"class_section_id": section_id}).json()
    assert all(i["student"]["class_section_id"] == section_id for i in by_class["items"])

    pid = first["id"]
    edited = client.put(
        f"/api/v1/interventions/{pid}",
        json={
            "plan_text": "Edited plan",
            "activities": [
                {
                    "title": "Reading",
                    "description": "Read daily",
                    "frequency": "Daily",
                    "owner": "parent",
                }
            ],
            "reassess_on": "2026-12-01",
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["plan_text"] == "Edited plan"
    assert edited.json()["activities"][0]["owner"] == "parent"
    bad = client.put(
        f"/api/v1/interventions/{pid}",
        json={"activities": [{"title": "x", "description": "y", "frequency": "z", "owner": "x"}]},
    )
    assert bad.status_code == 422

    approved = client.post(f"/api/v1/interventions/{pid}/approve").json()
    assert approved["status"] == "approved" and approved["approved_by"] == admin_ctx.user.id
    assert approved["approved_at"] and approved["approved_by_email"] == admin_ctx.user.email
    assert client.post(f"/api/v1/interventions/{pid}/approve").status_code == 409
    assert client.put(f"/api/v1/interventions/{pid}", json={"plan_text": "x"}).status_code == 409

    # approved -> in_progress -> completed (no skipping)
    assert (
        client.patch(
            f"/api/v1/interventions/{pid}/status", json={"status": "completed"}
        ).status_code
        == 409
    )
    for target in ("in_progress", "completed"):
        resp = client.patch(f"/api/v1/interventions/{pid}/status", json={"status": target})
        assert resp.status_code == 200 and resp.json()["status"] == target

    rest = [i["id"] for i in body["items"][1:]]
    rejected = client.post(f"/api/v1/interventions/{rest[0]}/reject", json={"reason": "Not needed"})
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["evidence"]["rejection"]["reason"] == "Not needed"

    assert db.get(AgentRun, run["id"]).status.value == "awaiting_approval"  # type: ignore[union-attr]
    for plan_id in rest[1:]:
        assert client.post(f"/api/v1/interventions/{plan_id}/approve").status_code == 200
    assert client.get(f"/api/v1/agent-runs/{run['id']}").json()["status"] == "done"

    actions = set(
        db.scalars(
            select(AuditLog.action).where(AuditLog.school_id == school.id, AuditLog.actor == "user")
        )
    )
    assert {
        "run_requested",
        "plan_edited",
        "plan_approved",
        "plan_rejected",
        "plan_status_changed",
    } <= actions
    closed = db.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.action == "run_closed", AuditLog.entity_id == run["id"]
        )
    )
    assert closed == 1


def test_teacher_can_only_review_taught_sections(
    db: Session,
    school: School,
    exam: Exam,
    make_tenant: MakeTenant,
    client_as: ClientAs,
    sync_executor: Any,
) -> None:
    start(client_as(make_tenant(MembershipRole.school_admin, school=school)), exam)
    plans = list(
        db.scalars(select(InterventionPlan).where(InterventionPlan.school_id == school.id))
    )
    students = {s.id: s for s in db.scalars(select(Student).where(Student.school_id == school.id))}
    sections = sorted(
        db.scalars(select(ClassSection.id).where(ClassSection.school_id == school.id))
    )
    mine = [p for p in plans if students[p.student_id].class_section_id == sections[0]]
    other = [p for p in plans if students[p.student_id].class_section_id == sections[1]]
    assert mine and other

    teacher = client_as(teacher_for_section(db, make_tenant, school, sections[0]))
    listing = teacher.get("/api/v1/interventions").json()
    assert {i["id"] for i in listing["items"]} == {p.id for p in mine}
    assert all(i["can_review"] for i in listing["items"])

    assert teacher.post(f"/api/v1/interventions/{other[0].id}/approve").status_code == 403
    assert teacher.post(f"/api/v1/interventions/{other[0].id}/reject", json={}).status_code == 403
    assert teacher.get(f"/api/v1/interventions/{other[0].id}").status_code == 403
    assert (
        teacher.put(f"/api/v1/interventions/{other[0].id}", json={"plan_text": "x"}).status_code
        == 403
    )
    ok = teacher.post(f"/api/v1/interventions/{mine[0].id}/approve")
    assert ok.status_code == 200 and ok.json()["status"] == "approved"

    # teacher without any assignment sees nothing and can approve nothing
    loner = client_as(make_tenant(MembershipRole.teacher, school=school))
    assert loner.get("/api/v1/interventions").json()["total"] == 0
    assert loner.post(f"/api/v1/interventions/{other[1].id}/approve").status_code == 403


def test_interventions_cross_tenant_404(
    db: Session,
    school: School,
    exam: Exam,
    make_tenant: MakeTenant,
    client_as: ClientAs,
    sync_executor: Any,
) -> None:
    start(client_as(make_tenant(MembershipRole.school_admin, school=school)), exam)
    plan = db.scalar(select(InterventionPlan).where(InterventionPlan.school_id == school.id))
    assert plan is not None
    other = client_as(make_tenant(MembershipRole.school_admin))
    assert other.get(f"/api/v1/interventions/{plan.id}").status_code == 404
    assert other.post(f"/api/v1/interventions/{plan.id}/approve").status_code == 404
    assert other.post(f"/api/v1/interventions/{plan.id}/reject", json={}).status_code == 404
    assert other.put(f"/api/v1/interventions/{plan.id}", json={"plan_text": "x"}).status_code == 404
    assert (
        other.patch(
            f"/api/v1/interventions/{plan.id}/status", json={"status": "in_progress"}
        ).status_code
        == 404
    )


# --- audit ---------------------------------------------------------------------------------


def test_audit_logs_listing_and_filters(
    db: Session,
    school: School,
    exam: Exam,
    make_tenant: MakeTenant,
    client_as: ClientAs,
    sync_executor: Any,
) -> None:
    admin_ctx = make_tenant(MembershipRole.school_admin, school=school)
    client = client_as(admin_ctx)
    start(client, exam)

    all_logs = client.get("/api/v1/audit-logs", params={"limit": 200}).json()
    assert all_logs["total"] > 5
    assert {"DataQualityAgent", "PerformanceAnalysisAgent", "InterventionAgent", "user"} <= set(
        all_logs["actors"]
    )
    times = [i["created_at"] for i in all_logs["items"]]
    assert times == sorted(times, reverse=True)
    user_rows = client.get("/api/v1/audit-logs", params={"actor": "user"}).json()["items"]
    assert user_rows and all(r["actor"] == "user" for r in user_rows)
    assert user_rows[0]["user_email"] == admin_ctx.user.email
    agents = client.get("/api/v1/audit-logs", params={"actor": "agents"}).json()["items"]
    assert agents and all(r["actor"] != "user" for r in agents)
    plans = client.get(
        "/api/v1/audit-logs", params={"entity_type": "intervention_plan", "limit": 5, "offset": 1}
    ).json()
    assert len(plans["items"]) == 5 and all(
        r["entity_type"] == "intervention_plan" for r in plans["items"]
    )

    teacher = client_as(make_tenant(MembershipRole.teacher, school=school))
    assert teacher.get("/api/v1/audit-logs").status_code == 403
    other = client_as(make_tenant(MembershipRole.school_admin))
    assert other.get("/api/v1/audit-logs").json()["total"] == 0
