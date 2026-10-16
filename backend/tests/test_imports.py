"""API tests for the marks import workflow (upload -> validate -> remap -> commit/reject)."""

import io
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import TenantContext
from app.models import (
    AcademicYear,
    AuditLog,
    ClassSection,
    Exam,
    ExamSubjectConfig,
    ImportBatch,
    Mark,
    MembershipRole,
    Student,
    Subject,
)

ClientFactory = Callable[[TenantContext], TestClient]
TenantFactory = Callable[..., TenantContext]


@dataclass
class Setup:
    exam: Exam
    maths: Subject
    science: Subject
    students: dict[str, Student]


@pytest.fixture(autouse=True)
def _uploads_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "UPLOADS_DIR", str(tmp_path / "uploads"))
    return tmp_path / "uploads"


def make_setup(db: Session, school_id: int) -> Setup:
    year = AcademicYear(school_id=school_id, label="2026-27", is_current=True)
    db.add(year)
    db.flush()
    sec_a = ClassSection(school_id=school_id, academic_year_id=year.id, grade=8, section="A")
    sec_b = ClassSection(school_id=school_id, academic_year_id=year.id, grade=9, section="B")
    maths = Subject(school_id=school_id, name="Mathematics", code="MATH")
    science = Subject(school_id=school_id, name="Science", code="SCI")
    db.add_all([sec_a, sec_b, maths, science])
    db.flush()
    exam = Exam(school_id=school_id, academic_year_id=year.id, name="Unit Test 1", sequence=1)
    db.add(exam)
    db.flush()
    db.add_all(
        [
            ExamSubjectConfig(
                school_id=school_id,
                exam_id=exam.id,
                subject_id=maths.id,
                max_marks=Decimal("100"),
                pass_marks=Decimal("35"),
            ),
            ExamSubjectConfig(
                school_id=school_id,
                exam_id=exam.id,
                subject_id=science.id,
                max_marks=Decimal("50"),
                pass_marks=Decimal("18"),
            ),
        ]
    )
    students: dict[str, Student] = {}
    for n, (adm, section) in enumerate(
        [("A001", sec_a), ("A002", sec_a), ("A003", sec_a), ("B001", sec_b)], start=1
    ):
        st = Student(
            school_id=school_id,
            class_section_id=section.id,
            admission_no=adm,
            full_name=f"Student {adm}",
            pseudo_id=f"S-{school_id}-{n:04d}",
        )
        db.add(st)
        students[adm] = st
    db.flush()
    return Setup(exam=exam, maths=maths, science=science, students=students)


GOOD_CSV = b"Admission No,Name,Maths,Science\nA001,Asha,78,40\nA002,Ravi,AB,35.5\nA003,Meera,90,\n"


def upload(
    client: TestClient, exam_id: int, content: bytes, name: str = "marks.csv"
) -> httpx.Response:
    return client.post(
        "/api/v1/imports",
        data={"exam_id": str(exam_id)},
        files={"file": (name, content, "text/csv")},
    )


def test_upload_validate_commit_flow(
    db: Session, make_tenant: TenantFactory, client_as: ClientFactory, _uploads_dir: Path
) -> None:
    ctx = make_tenant(MembershipRole.teacher)
    s = make_setup(db, ctx.school_id)
    client = client_as(ctx)

    res = upload(client, s.exam.id, GOOD_CSV)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "validated"
    assert body["headers"] == ["Admission No", "Name", "Maths", "Science"]
    assert body["column_map"] == {
        "admission_column": "Admission No",
        "subjects": {"Name": None, "Maths": s.maths.id, "Science": s.science.id},
    }
    assert body["row_count"] == 3
    assert body["summary"]["errors"] == 0
    assert body["summary"]["by_code"] == {"ABSENT": 1, "MISSING_MARK": 1}
    assert body["can_commit"] is True
    assert body["preview"][1]["marks"]["Maths"]["is_absent"] is True
    assert {e["name"] for e in body["exam_subjects"]} == {"Mathematics", "Science"}
    assert "Checked 3 rows" in body["summary_text"]

    batch_id = body["id"]
    stored = list((_uploads_dir / str(ctx.school_id)).iterdir())
    assert [p.name for p in stored] == [f"{batch_id}_marks.csv"]

    assert client.get(f"/api/v1/imports/{batch_id}").json()["id"] == batch_id
    listed = client.get("/api/v1/imports", params={"exam_id": s.exam.id}).json()
    assert [b["id"] for b in listed] == [batch_id]
    assert listed[0]["exam_name"] == "Unit Test 1"

    res = client.post(f"/api/v1/imports/{batch_id}/commit")
    assert res.status_code == 200, res.text
    assert res.json() == {
        "batch_id": batch_id,
        "inserted": 5,
        "updated": 0,
        "absent": 1,
        "skipped": 1,
    }

    marks = {
        (m.student_id, m.subject_id): m
        for m in db.scalars(select(Mark).where(Mark.exam_id == s.exam.id))
    }
    assert len(marks) == 5
    assert marks[(s.students["A001"].id, s.maths.id)].marks_obtained == Decimal("78")
    absent = marks[(s.students["A002"].id, s.maths.id)]
    assert absent.is_absent is True and absent.marks_obtained is None
    assert (s.students["A003"].id, s.science.id) not in marks  # blank cell skipped

    assert client.get(f"/api/v1/imports/{batch_id}").json()["status"] == "committed"
    # Committing the same batch twice is a conflict.
    assert client.post(f"/api/v1/imports/{batch_id}/commit").status_code == 409

    actions = set(
        db.scalars(
            select(AuditLog.action).where(
                AuditLog.school_id == ctx.school_id, AuditLog.entity_id == batch_id
            )
        )
    )
    assert {"import.upload", "import.commit"} <= actions


def test_recommit_updates_instead_of_duplicating(
    db: Session, make_tenant: TenantFactory, client_as: ClientFactory
) -> None:
    ctx = make_tenant()
    s = make_setup(db, ctx.school_id)
    client = client_as(ctx)

    first = upload(client, s.exam.id, GOOD_CSV).json()
    assert client.post(f"/api/v1/imports/{first['id']}/commit").json()["inserted"] == 5

    corrected = GOOD_CSV.replace(b"A001,Asha,78,40", b"A001,Asha,80,41")
    second = upload(client, s.exam.id, corrected).json()
    result = client.post(f"/api/v1/imports/{second['id']}/commit").json()
    assert (result["inserted"], result["updated"]) == (0, 5)

    count = db.scalar(select(func.count()).select_from(Mark).where(Mark.exam_id == s.exam.id))
    assert count == 5
    mark = db.scalar(
        select(Mark).where(Mark.student_id == s.students["A001"].id, Mark.subject_id == s.maths.id)
    )
    assert mark is not None and mark.marks_obtained == Decimal("80")


def test_commit_blocked_when_errors(
    db: Session, make_tenant: TenantFactory, client_as: ClientFactory
) -> None:
    ctx = make_tenant()
    s = make_setup(db, ctx.school_id)
    client = client_as(ctx)
    bad = b"adm no,Maths,Science\nA001,120,40\nZZZ,10,10\nA002,x,-3\nA001,1,1\n"
    body = upload(client, s.exam.id, bad).json()
    assert body["can_commit"] is False
    assert body["summary"]["by_code"] == {
        "DUPLICATE_STUDENT_ROW": 1,
        "MARK_ABOVE_MAX": 1,
        "NEGATIVE_MARK": 1,
        "NON_NUMERIC": 1,
        "STUDENT_NOT_IN_FILE": 1,
        "UNKNOWN_STUDENT": 1,
    }
    res = client.post(f"/api/v1/imports/{body['id']}/commit")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "IMPORT_HAS_ERRORS"
    assert db.scalar(select(func.count()).select_from(Mark)) == 0


def test_xlsx_upload_and_remap(
    db: Session, make_tenant: TenantFactory, client_as: ClientFactory
) -> None:
    ctx = make_tenant(MembershipRole.coordinator)
    s = make_setup(db, ctx.school_id)
    client = client_as(ctx)

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["Student", "Paper 1", "Paper 2"])
    ws.append(["A001", 50, 20])
    ws.append(["A002", 60, 30])
    ws.append(["A003", 70, 45])
    buf = io.BytesIO()
    wb.save(buf)

    body = upload(client, s.exam.id, buf.getvalue(), "marks.xlsx").json()
    assert body["column_map"]["admission_column"] is None
    assert body["summary"]["by_code"] == {"NO_ADMISSION_COLUMN": 1}
    assert body["can_commit"] is False

    res = client.put(
        f"/api/v1/imports/{body['id']}/mapping",
        json={
            "admission_column": "Student",
            "subjects": {"Paper 1": s.maths.id, "Paper 2": s.science.id},
        },
    )
    assert res.status_code == 200, res.text
    remapped = res.json()
    assert remapped["summary"]["errors"] == 0
    assert remapped["can_commit"] is True
    assert remapped["preview"][0]["marks"]["Paper 1"]["value"] == "50"

    # Invalid mappings are rejected.
    bad_requests = [
        {"admission_column": "Nope", "subjects": {}},
        {"admission_column": "Student", "subjects": {"Paper 1": 999999}},
        {"admission_column": "Student", "subjects": {"Paper 1": s.maths.id, "Paper 2": s.maths.id}},
    ]
    for payload in bad_requests:
        assert client.put(f"/api/v1/imports/{body['id']}/mapping", json=payload).status_code == 422

    assert client.post(f"/api/v1/imports/{body['id']}/commit").json()["inserted"] == 6


def test_reject_and_upload_errors(
    db: Session, make_tenant: TenantFactory, client_as: ClientFactory
) -> None:
    ctx = make_tenant()
    s = make_setup(db, ctx.school_id)
    client = client_as(ctx)

    body = upload(client, s.exam.id, GOOD_CSV).json()
    res = client.post(f"/api/v1/imports/{body['id']}/reject")
    assert res.status_code == 200 and res.json()["status"] == "rejected"
    assert client.post(f"/api/v1/imports/{body['id']}/commit").status_code == 409
    remap = {"admission_column": "Admission No", "subjects": {}}
    assert client.put(f"/api/v1/imports/{body['id']}/mapping", json=remap).status_code == 409

    res = upload(client, s.exam.id, b"%PDF", "marks.pdf")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
    assert upload(client, 999999, GOOD_CSV).status_code == 404


def test_template_csv(db: Session, make_tenant: TenantFactory, client_as: ClientFactory) -> None:
    ctx = make_tenant()
    s = make_setup(db, ctx.school_id)
    res = client_as(ctx).get("/api/v1/imports/template", params={"exam_id": s.exam.id})
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert "marks_template_unit_test_1.csv" in res.headers["content-disposition"]
    lines = res.text.strip().splitlines()
    assert lines[0] == "admission_no,Mathematics,Science"
    assert lines[1:] == ["A001,,", "A002,,", "A003,,", "B001,,"]


def test_cross_tenant_isolation(
    db: Session, make_tenant: TenantFactory, client_as: ClientFactory
) -> None:
    owner = make_tenant()
    s = make_setup(db, owner.school_id)
    batch_id = upload(client_as(owner), s.exam.id, GOOD_CSV).json()["id"]

    other = make_tenant()
    make_setup(db, other.school_id)
    client = client_as(other)
    assert client.get(f"/api/v1/imports/{batch_id}").status_code == 404
    assert client.post(f"/api/v1/imports/{batch_id}/commit").status_code == 404
    assert client.post(f"/api/v1/imports/{batch_id}/reject").status_code == 404
    remap = {"admission_column": "Admission No", "subjects": {}}
    assert client.put(f"/api/v1/imports/{batch_id}/mapping", json=remap).status_code == 404
    assert client.get("/api/v1/imports").json() == []
    # The other school's exam is invisible too.
    assert upload(client, s.exam.id, GOOD_CSV).status_code == 404
    assert client.get("/api/v1/imports/template", params={"exam_id": s.exam.id}).status_code == 404
    # Owner's batch is untouched.
    batch = db.get(ImportBatch, batch_id)
    assert batch is not None and batch.status.value == "validated"
