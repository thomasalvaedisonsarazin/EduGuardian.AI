"""Module 2 (Academic Setup) API tests: CRUD, validation, tenancy, conflicts."""

from collections.abc import Callable
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import TenantContext
from app.models import AuditLog, Mark, MembershipRole, School, Student
from app.services.setup_service import next_pseudo_id

ClientAs = Callable[[TenantContext], TestClient]
MakeTenant = Callable[..., TenantContext]


def _ok(resp: Any, status: int = 200) -> Any:
    assert resp.status_code == status, resp.text
    return resp.json()


@pytest.fixture()
def admin(make_tenant: MakeTenant) -> TenantContext:
    return make_tenant(MembershipRole.school_admin)


@pytest.fixture()
def api(admin: TenantContext, client_as: ClientAs) -> TestClient:
    return client_as(admin)


def _setup_basics(api: TestClient) -> dict[str, int]:
    year = _ok(
        api.post("/api/v1/academic-years", json={"label": "2026-27", "is_current": True}), 201
    )
    cls = _ok(
        api.post(
            "/api/v1/classes", json={"academic_year_id": year["id"], "grade": 10, "section": "a"}
        ),
        201,
    )
    subj = _ok(api.post("/api/v1/subjects", json={"name": "Mathematics", "code": "MATH"}), 201)
    exam = _ok(
        api.post(
            "/api/v1/exams",
            json={"academic_year_id": year["id"], "name": "Unit Test 1", "sequence": 1},
        ),
        201,
    )
    student = _ok(
        api.post(
            "/api/v1/students",
            json={"class_section_id": cls["id"], "admission_no": "A1", "full_name": "Asha Rao"},
        ),
        201,
    )
    return {
        "year": year["id"],
        "class": cls["id"],
        "subject": subj["id"],
        "exam": exam["id"],
        "student": student["id"],
    }


# --- academic years ---------------------------------------------------------------------------
def test_academic_year_crud_and_single_current(api: TestClient, db: Session) -> None:
    y1 = _ok(api.post("/api/v1/academic-years", json={"label": "2025-26", "is_current": True}), 201)
    y2 = _ok(api.post("/api/v1/academic-years", json={"label": "2026-27", "is_current": True}), 201)
    years = {y["label"]: y for y in _ok(api.get("/api/v1/academic-years"))}
    assert years["2026-27"]["is_current"] is True
    assert years["2025-26"]["is_current"] is False

    _ok(api.patch(f"/api/v1/academic-years/{y1['id']}", json={"is_current": True}))
    years = {y["label"]: y for y in _ok(api.get("/api/v1/academic-years"))}
    assert years["2025-26"]["is_current"] and not years["2026-27"]["is_current"]

    dup = api.post("/api/v1/academic-years", json={"label": "2025-26"})
    assert dup.status_code == 409

    assert api.delete(f"/api/v1/academic-years/{y2['id']}").status_code == 204
    assert api.get(f"/api/v1/academic-years/{y2['id']}").status_code == 404
    actions = set(db.scalars(select(AuditLog.action)).all())
    assert {"academic_year.create", "academic_year.update", "academic_year.delete"} <= actions


def test_validation_errors(api: TestClient) -> None:
    assert api.post("/api/v1/academic-years", json={"label": ""}).status_code == 422
    ids = _setup_basics(api)
    bad_grade = {"academic_year_id": ids["year"], "grade": 13, "section": "A"}
    assert api.post("/api/v1/classes", json=bad_grade).status_code == 422
    dup_class = {"academic_year_id": ids["year"], "grade": 10, "section": "A"}
    assert api.post("/api/v1/classes", json=dup_class).status_code == 409
    assert api.post("/api/v1/subjects", json={"name": "X", "code": "MATH"}).status_code == 409


# --- classes ----------------------------------------------------------------------------------
def test_classes_filter_and_student_count(api: TestClient) -> None:
    ids = _setup_basics(api)
    other_year = _ok(api.post("/api/v1/academic-years", json={"label": "2027-28"}), 201)
    _ok(
        api.post(
            "/api/v1/classes",
            json={"academic_year_id": other_year["id"], "grade": 9, "section": "B"},
        ),
        201,
    )
    classes = _ok(api.get("/api/v1/classes", params={"academic_year_id": ids["year"]}))
    assert len(classes) == 1
    assert classes[0]["section"] == "A"  # normalised to upper case
    assert classes[0]["student_count"] == 1
    assert len(_ok(api.get("/api/v1/classes"))) == 2

    updated = _ok(api.patch(f"/api/v1/classes/{ids['class']}", json={"section": "c"}))
    assert updated["section"] == "C"


# --- teachers & assignments -------------------------------------------------------------------
def test_teachers_and_assignments(api: TestClient, admin: TenantContext) -> None:
    ids = _setup_basics(api)
    t1 = _ok(api.post("/api/v1/teachers", json={"full_name": "Rajesh Kumar"}), 201)
    t2 = _ok(
        api.post("/api/v1/teachers", json={"full_name": "Anita", "user_id": admin.user.id}), 201
    )
    assert t2["user_id"] == admin.user.id
    payload = {"class_section_id": ids["class"], "subject_id": ids["subject"]}
    a1 = _ok(
        api.post(
            "/api/v1/teaching-assignments",
            json={**payload, "teacher_id": t1["id"], "is_class_teacher": True},
        ),
        201,
    )
    dup = api.post("/api/v1/teaching-assignments", json={**payload, "teacher_id": t1["id"]})
    assert dup.status_code == 409
    a2 = _ok(
        api.post(
            "/api/v1/teaching-assignments",
            json={**payload, "teacher_id": t2["id"], "is_class_teacher": True},
        ),
        201,
    )
    # only one class teacher per section
    rows = {
        r["id"]: r
        for r in _ok(
            api.get("/api/v1/teaching-assignments", params={"class_section_id": ids["class"]})
        )
    }
    assert rows[a2["id"]]["is_class_teacher"] and not rows[a1["id"]]["is_class_teacher"]
    by_teacher = _ok(api.get("/api/v1/teaching-assignments", params={"teacher_id": t1["id"]}))
    assert [r["id"] for r in by_teacher] == [a1["id"]]

    # deleting a teacher cascades to their assignments
    assert api.delete(f"/api/v1/teachers/{t1['id']}").status_code == 204
    assert api.get(f"/api/v1/teaching-assignments/{a1['id']}").status_code == 404


def test_teacher_user_must_belong_to_school(
    api: TestClient, make_tenant: MakeTenant, client_as: ClientAs
) -> None:
    outsider = make_tenant()
    api = client_as(make_tenant())
    resp = api.post("/api/v1/teachers", json={"full_name": "X", "user_id": outsider.user.id})
    assert resp.status_code == 404


# --- students ---------------------------------------------------------------------------------
def test_student_pseudo_id_sequence(api: TestClient, admin: TenantContext, db: Session) -> None:
    ids = _setup_basics(api)
    assert _ok(api.get(f"/api/v1/students/{ids['student']}"))["pseudo_id"] == "S-0001"
    s2 = _ok(
        api.post(
            "/api/v1/students",
            json={"class_section_id": ids["class"], "admission_no": "A2", "full_name": "Bina"},
        ),
        201,
    )
    assert s2["pseudo_id"] == "S-0002"
    # gaps are not reused: next = max existing + 1
    db.add(
        Student(
            school_id=admin.school_id,
            class_section_id=ids["class"],
            admission_no="A9",
            full_name="Manual",
            pseudo_id="S-0041",
        )
    )
    db.flush()
    assert next_pseudo_id(db, admin.school_id) == "S-0042"
    dup = api.post(
        "/api/v1/students",
        json={"class_section_id": ids["class"], "admission_no": "A2", "full_name": "Dup"},
    )
    assert dup.status_code == 409


def test_pseudo_ids_are_per_school(make_tenant: MakeTenant, client_as: ClientAs) -> None:
    a, b = make_tenant(), make_tenant()
    _setup_basics(client_as(a))
    api_b = client_as(b)
    ids_b = _setup_basics(api_b)
    assert _ok(api_b.get(f"/api/v1/students/{ids_b['student']}"))["pseudo_id"] == "S-0001"


def test_student_list_filter_search_pagination(api: TestClient) -> None:
    ids = _setup_basics(api)
    for i in range(2, 8):
        _ok(
            api.post(
                "/api/v1/students",
                json={
                    "class_section_id": ids["class"],
                    "admission_no": f"A{i}",
                    "full_name": f"Student {i}",
                },
            ),
            201,
        )
    page = _ok(api.get("/api/v1/students", params={"limit": 3, "offset": 0}))
    assert page["total"] == 7 and len(page["items"]) == 3
    page2 = _ok(api.get("/api/v1/students", params={"limit": 3, "offset": 6}))
    assert len(page2["items"]) == 1
    found = _ok(api.get("/api/v1/students", params={"q": "asha"}))
    assert found["total"] == 1 and found["items"][0]["admission_no"] == "A1"
    by_class = _ok(api.get("/api/v1/students", params={"class_section_id": ids["class"]}))
    assert by_class["total"] == 7
    assert api.get("/api/v1/students", params={"limit": 0}).status_code == 422


# --- exams ------------------------------------------------------------------------------------
def test_exams_ordering_and_subject_configs(api: TestClient) -> None:
    ids = _setup_basics(api)
    _ok(
        api.post(
            "/api/v1/exams",
            json={"academic_year_id": ids["year"], "name": "Final", "sequence": 3},
        ),
        201,
    )
    _ok(
        api.post(
            "/api/v1/exams",
            json={"academic_year_id": ids["year"], "name": "Quarterly", "sequence": 2},
        ),
        201,
    )
    exams = _ok(api.get("/api/v1/exams", params={"academic_year_id": ids["year"]}))
    assert [e["name"] for e in exams] == ["Unit Test 1", "Quarterly", "Final"]

    english = _ok(api.post("/api/v1/subjects", json={"name": "English", "code": "ENG"}), 201)
    url = f"/api/v1/exams/{ids['exam']}/subjects"
    configs = [
        {"subject_id": ids["subject"], "max_marks": 100, "pass_marks": 35},
        {"subject_id": english["id"], "max_marks": 50, "pass_marks": 18},
    ]
    out = _ok(api.put(url, json=configs))
    assert {c["subject_name"] for c in out} == {"Mathematics", "English"}
    # replace-all: drop English, update Math
    out = _ok(
        api.put(url, json=[{"subject_id": ids["subject"], "max_marks": 80, "pass_marks": 30}])
    )
    assert len(out) == 1 and Decimal(str(out[0]["max_marks"])) == Decimal("80")
    assert len(_ok(api.get(url))) == 1

    bad = [{"subject_id": ids["subject"], "max_marks": 50, "pass_marks": 60}]
    assert api.put(url, json=bad).status_code == 422
    dup = [{"subject_id": ids["subject"], "max_marks": 50, "pass_marks": 20}] * 2
    assert api.put(url, json=dup).status_code == 422


# --- delete conflicts -------------------------------------------------------------------------
def test_delete_conflicts_when_marks_exist(
    api: TestClient, admin: TenantContext, db: Session
) -> None:
    ids = _setup_basics(api)
    url = f"/api/v1/exams/{ids['exam']}/subjects"
    _ok(api.put(url, json=[{"subject_id": ids["subject"], "max_marks": 100, "pass_marks": 35}]))
    db.add(
        Mark(
            school_id=admin.school_id,
            exam_id=ids["exam"],
            student_id=ids["student"],
            subject_id=ids["subject"],
            marks_obtained=Decimal("50"),
        )
    )
    db.flush()
    for path in (
        f"/api/v1/students/{ids['student']}",
        f"/api/v1/subjects/{ids['subject']}",
        f"/api/v1/exams/{ids['exam']}",
        f"/api/v1/classes/{ids['class']}",
        f"/api/v1/academic-years/{ids['year']}",
    ):
        resp = api.delete(path)
        assert resp.status_code == 409, path
        assert "marks" in resp.json()["error"]["message"]
    assert api.put(url, json=[]).status_code == 409


def test_delete_without_marks_cascades(api: TestClient) -> None:
    ids = _setup_basics(api)
    assert api.delete(f"/api/v1/classes/{ids['class']}").status_code == 204
    assert api.get(f"/api/v1/students/{ids['student']}").status_code == 404


# --- auth & tenancy ---------------------------------------------------------------------------
def test_teacher_can_read_but_not_write(
    make_tenant: MakeTenant, client_as: ClientAs, db: Session
) -> None:
    admin = make_tenant()
    _setup_basics(client_as(admin))
    teacher = make_tenant(MembershipRole.teacher, school=db.get(School, admin.school_id))
    api = client_as(teacher)
    assert len(_ok(api.get("/api/v1/subjects"))) == 1
    assert api.post("/api/v1/subjects", json={"name": "Art", "code": "ART"}).status_code == 403


def test_cross_tenant_isolation(make_tenant: MakeTenant, client_as: ClientAs) -> None:
    a, b = make_tenant(), make_tenant()
    ids = _setup_basics(client_as(a))
    api_b = client_as(b)
    for path in (
        f"/api/v1/academic-years/{ids['year']}",
        f"/api/v1/classes/{ids['class']}",
        f"/api/v1/subjects/{ids['subject']}",
        f"/api/v1/exams/{ids['exam']}",
        f"/api/v1/exams/{ids['exam']}/subjects",
        f"/api/v1/students/{ids['student']}",
    ):
        assert api_b.get(path).status_code == 404, path
        if not path.endswith("/subjects") or "/exams/" not in path:
            assert api_b.delete(path).status_code == 404, path
    assert (
        api_b.patch(f"/api/v1/students/{ids['student']}", json={"full_name": "X"}).status_code
        == 404
    )
    assert _ok(api_b.get("/api/v1/students"))["total"] == 0
    assert _ok(api_b.get("/api/v1/classes")) == []

    # foreign ids in payloads are rejected as 404
    year_b = _ok(api_b.post("/api/v1/academic-years", json={"label": "2026-27"}), 201)
    assert (
        api_b.post(
            "/api/v1/classes", json={"academic_year_id": ids["year"], "grade": 1, "section": "A"}
        ).status_code
        == 404
    )
    assert (
        api_b.post(
            "/api/v1/students",
            json={"class_section_id": ids["class"], "admission_no": "Z", "full_name": "Z"},
        ).status_code
        == 404
    )
    exam_b = _ok(
        api_b.post(
            "/api/v1/exams", json={"academic_year_id": year_b["id"], "name": "UT", "sequence": 1}
        ),
        201,
    )
    resp = api_b.put(
        f"/api/v1/exams/{exam_b['id']}/subjects",
        json=[{"subject_id": ids["subject"], "max_marks": 100, "pass_marks": 35}],
    )
    assert resp.status_code == 404
    teacher_b = _ok(api_b.post("/api/v1/teachers", json={"full_name": "T"}), 201)
    resp = api_b.post(
        "/api/v1/teaching-assignments",
        json={
            "teacher_id": teacher_b["id"],
            "class_section_id": ids["class"],
            "subject_id": ids["subject"],
        },
    )
    assert resp.status_code == 404
