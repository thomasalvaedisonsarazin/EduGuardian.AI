"""Loader/service/endpoint tests for Module 4 analytics (same hand-computed fixture as
test_analytics_calculations.py, persisted through the ORM)."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.analytics.loader import load_exam_dataset, previous_exam_id
from app.analytics.service import (
    dashboard_overview,
    exam_overview,
    student_trend,
    teacher_view,
)
from app.dependencies import TenantContext
from app.exceptions import NotFoundError
from app.models import (
    AcademicYear,
    ClassSection,
    Exam,
    ExamSubjectConfig,
    Mark,
    Student,
    Subject,
    Teacher,
    TeachingAssignment,
)

D = Decimal
BASE = "/api/v1/analytics"

CURRENT = {
    1: ("90", "85", "45"),
    2: ("70", "60", "40"),
    3: ("70", "60", "40"),
    4: ("30", None, "20"),  # None = absent
    5: ("50", "40", "17"),
    6: ("34.5", "34", "10"),
}
PREVIOUS = {
    1: ("80", "80", "40"),
    2: ("90", "85", "45"),
    3: ("60", "60", "30"),
    4: ("40", "40", "20"),
    5: ("50", "50", "25"),
    6: ("35", "35", "18"),
}


@dataclass
class World:
    school_id: int
    exam1: int
    exam2: int
    exam3_empty: int
    sec_a: int
    sec_b: int
    sec_c_empty: int
    maths: int
    science: int
    english: int
    students: dict[int, int]  # fixture number -> db id
    teacher: int
    teacher_unassigned: int


def build_world(db: Session, school_id: int) -> World:
    year = AcademicYear(school_id=school_id, label="2026-27", is_current=True)
    db.add(year)
    db.flush()
    sec_a = ClassSection(school_id=school_id, academic_year_id=year.id, grade=8, section="A")
    sec_b = ClassSection(school_id=school_id, academic_year_id=year.id, grade=8, section="B")
    sec_c = ClassSection(school_id=school_id, academic_year_id=year.id, grade=9, section="A")
    db.add_all([sec_a, sec_b, sec_c])
    maths = Subject(school_id=school_id, name="Maths", code=f"M{school_id}")
    science = Subject(school_id=school_id, name="Science", code=f"S{school_id}")
    english = Subject(school_id=school_id, name="English", code=f"E{school_id}")
    db.add_all([maths, science, english])
    db.flush()

    students: dict[int, int] = {}
    for n in range(1, 7):
        st = Student(
            school_id=school_id,
            class_section_id=sec_a.id if n <= 4 else sec_b.id,
            admission_no=f"ADM{n}",
            full_name=f"Student {n}",
            pseudo_id=f"S-{n:04d}",
        )
        db.add(st)
        db.flush()
        students[n] = st.id

    def make_exam(name: str, seq: int, table: dict[int, tuple[str | None, ...]] | None) -> int:
        exam = Exam(
            school_id=school_id,
            academic_year_id=year.id,
            name=name,
            sequence=seq,
            held_on=date(2026, seq * 3, 1),
        )
        db.add(exam)
        db.flush()
        for subject, max_m, pass_m in ((maths, 100, 35), (science, 100, 35), (english, 50, 18)):
            db.add(
                ExamSubjectConfig(
                    school_id=school_id,
                    exam_id=exam.id,
                    subject_id=subject.id,
                    max_marks=D(max_m),
                    pass_marks=D(pass_m),
                )
            )
        for n, values in (table or {}).items():
            for subject, value in zip((maths, science, english), values, strict=True):
                db.add(
                    Mark(
                        school_id=school_id,
                        exam_id=exam.id,
                        student_id=students[n],
                        subject_id=subject.id,
                        marks_obtained=D(value) if value is not None else None,
                        is_absent=value is None,
                    )
                )
        db.flush()
        return exam.id

    exam1 = make_exam("Unit Test 1", 1, PREVIOUS)
    exam2 = make_exam("Unit Test 2", 2, CURRENT)
    exam3 = make_exam("Term 1", 3, None)

    teacher = Teacher(school_id=school_id, full_name="Ms. Rao")
    idle = Teacher(school_id=school_id, full_name="Mr. Idle")
    db.add_all([teacher, idle])
    db.flush()
    for section, subject in ((sec_a, maths), (sec_b, maths), (sec_a, english)):
        db.add(
            TeachingAssignment(
                school_id=school_id,
                teacher_id=teacher.id,
                class_section_id=section.id,
                subject_id=subject.id,
                is_class_teacher=section is sec_a and subject is maths,
            )
        )
    db.flush()
    return World(
        school_id=school_id,
        exam1=exam1,
        exam2=exam2,
        exam3_empty=exam3,
        sec_a=sec_a.id,
        sec_b=sec_b.id,
        sec_c_empty=sec_c.id,
        maths=maths.id,
        science=science.id,
        english=english.id,
        students=students,
        teacher=teacher.id,
        teacher_unassigned=idle.id,
    )


@pytest.fixture()
def ctx(make_tenant: Callable[..., TenantContext]) -> TenantContext:
    return make_tenant(role="teacher")


@pytest.fixture()
def world(db: Session, ctx: TenantContext) -> World:
    return build_world(db, ctx.school_id)


# ---------------------------------------------------------------------------
# Loader / service
# ---------------------------------------------------------------------------


def test_loader_population_and_previous_exam(db: Session, world: World) -> None:
    ds = load_exam_dataset(db, world.school_id, world.exam2)
    assert [s.pseudo_id for s in ds.students] == [f"S-{n:04d}" for n in range(1, 7)]
    assert [c.name for c in ds.configs] == ["English", "Maths", "Science"]
    assert len(ds.marks) == 18
    assert ds.students[0].class_label == "8-A"
    assert previous_exam_id(db, world.school_id, world.exam2) == world.exam1
    assert previous_exam_id(db, world.school_id, world.exam1) is None
    # exam 3 has no marks; its comparison is exam 2. Its population is empty.
    assert previous_exam_id(db, world.school_id, world.exam3_empty) == world.exam2
    assert load_exam_dataset(db, world.school_id, world.exam3_empty).students == []


def test_exam_overview_matches_hand_computed(db: Session, world: World) -> None:
    ov = exam_overview(db, world.school_id, world.exam2)
    assert ov.comparison_exam_id == world.exam1
    assert ov.previous_exam is not None and ov.previous_exam.name == "Unit Test 1"
    assert ov.school_summary.pass_percentage == D("50.00")
    assert ov.school_summary.mean_percentage == D("53.03")
    assert ov.school_summary.median_percentage == D("55.40")
    assert [(c.class_label, c.pass_percentage) for c in ov.class_summaries] == [
        ("8-A", D("75.00")),
        ("8-B", D("0.00")),
    ]
    s = world.students
    assert [a.student_id for a in ov.at_risk] == [s[4], s[6], s[5], s[2]]
    by_id = {r.student_id: r for r in ov.results}
    assert [by_id[s[i]].rank_in_section for i in (1, 2, 3, 4, 5, 6)] == [1, 2, 2, 4, 1, 2]
    maths = next(x for x in ov.subject_summaries if x.subject_id == world.maths)
    assert maths.mean_percentage_change == D("-1.75")
    assert maths.weakest_sections == [world.sec_b]
    payload = ov.to_dict()
    assert payload["school_summary"]["pass_percentage"] == "50.00"


def test_exam_overview_section_filter_and_first_exam(db: Session, world: World) -> None:
    ov = exam_overview(db, world.school_id, world.exam2, [world.sec_b])
    assert {r.class_label for r in ov.results} == {"8-B"}
    assert ov.school_summary.class_label == "Selected classes"
    assert ov.school_summary.mean_percentage == D("37.10")

    first = exam_overview(db, world.school_id, world.exam1)
    assert first.comparison_exam_id is None and first.changes == []
    assert all(r.code != "SHARP_DROP" for a in first.at_risk for r in a.reasons)


def test_teacher_view_is_coaching_not_ranking(db: Session, world: World) -> None:
    view = teacher_view(db, world.school_id, world.teacher, world.exam2)
    keys = [(a.class_label, a.subject_name) for a in view.assignments]
    assert keys == [("8-A", "English"), ("8-A", "Maths"), ("8-B", "Maths")]
    maths_a = view.assignments[1]
    assert maths_a.stats is not None
    assert maths_a.stats.pass_percentage == D("75.00")
    assert maths_a.mean_change_points == D("-2.50")  # (+10 -20 +10 -10) / 4
    assert [x.pseudo_id for x in maths_a.students_needing_support] == ["S-0004"]
    assert maths_a.is_class_teacher is True
    assert view.combined is not None
    assert (view.combined.student_count, view.combined.pass_count) == (10, 8)
    assert any("below the pass mark" in n for n in maths_a.notes)
    payload = view.to_dict()
    assert "rank" not in str(payload.keys()) and "score" not in payload

    idle = teacher_view(db, world.school_id, world.teacher_unassigned, world.exam2)
    assert idle.assignments == [] and idle.combined is None


def test_student_trend(db: Session, world: World) -> None:
    trend = student_trend(db, world.school_id, world.students[2])
    assert [p.exam.name for p in trend.points] == ["Unit Test 1", "Unit Test 2"]
    assert [p.result.percentage for p in trend.points] == [D("88.00"), D("68.00")]
    assert [p.result.rank_in_section for p in trend.points] == [1, 2]
    assert trend.points[0].change is None and trend.points[0].at_risk is None
    last = trend.points[1]
    assert last.change is not None and last.change.delta == D("-20.00")
    assert last.at_risk is not None
    assert [r.code for r in last.at_risk.reasons] == ["SHARP_DROP"]
    assert last.section_pass_percentage == D("75.00")


def test_dashboard_overview(db: Session, world: World) -> None:
    dash = dashboard_overview(db, world.school_id)
    assert dash.student_count == 6
    assert dash.exams_with_marks == 2
    assert dash.latest_exam is not None and dash.latest_exam.id == world.exam2
    assert dash.at_risk_count == 4 and dash.at_risk_high_count == 2
    assert [t.pass_percentage for t in dash.trend] == [D("100.00"), D("50.00")]


def test_dashboard_overview_empty_school(
    db: Session, make_tenant: Callable[..., TenantContext]
) -> None:
    other = make_tenant()
    dash = dashboard_overview(db, other.school_id)
    assert dash.latest_exam is None and dash.summary is None and dash.trend == []


def test_service_foreign_ids_raise_not_found(
    db: Session, world: World, make_tenant: Callable[..., TenantContext]
) -> None:
    other = make_tenant()
    with pytest.raises(NotFoundError):
        exam_overview(db, other.school_id, world.exam2)
    with pytest.raises(NotFoundError):
        teacher_view(db, other.school_id, world.teacher, world.exam2)
    with pytest.raises(NotFoundError):
        student_trend(db, other.school_id, world.students[1])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def test_summary_endpoint(
    client_as: Callable[[TenantContext], TestClient], ctx: TenantContext, world: World
) -> None:
    res = client_as(ctx).get(f"{BASE}/exams/{world.exam2}/summary")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["school_summary"]["pass_percentage"] == "50.00"
    assert body["school_summary"]["median_percentage"] == "55.40"
    assert body["comparison_exam_id"] == world.exam1
    assert body["at_risk_count"] == 4 and body["at_risk_high_count"] == 2
    assert [b["count"] for b in body["school_summary"]["distribution"]] == [2, 1, 2, 1, 0]
    assert "results" not in body

    filtered = client_as(ctx).get(
        f"{BASE}/exams/{world.exam2}/summary", params={"class_section_ids": f"{world.sec_a}"}
    )
    assert filtered.json()["school_summary"]["student_count"] == 4
    bad = client_as(ctx).get(
        f"{BASE}/exams/{world.exam2}/summary", params={"class_section_ids": "x,1"}
    )
    assert bad.status_code == 422


def test_class_endpoint(
    client_as: Callable[[TenantContext], TestClient], ctx: TenantContext, world: World
) -> None:
    c = client_as(ctx)
    body = c.get(f"{BASE}/exams/{world.exam2}/classes/{world.sec_a}").json()
    assert body["class_label"] == "8-A"
    assert body["summary"]["pass_percentage"] == "75.00"
    assert [r["rank_in_section"] for r in body["results"]] == [1, 2, 2, 4]
    assert {ch["student_id"]: ch["delta"] for ch in body["changes"]}[world.students[2]] == (
        "-20.00"
    )
    assert [a["pseudo_id"] for a in body["at_risk"]] == ["S-0004", "S-0002"]

    empty = c.get(f"{BASE}/exams/{world.exam2}/classes/{world.sec_c_empty}")
    assert empty.status_code == 200
    assert empty.json()["summary"]["student_count"] == 0
    assert empty.json()["summary"]["pass_percentage"] is None
    assert empty.json()["results"] == []


def test_subject_endpoint(
    client_as: Callable[[TenantContext], TestClient], ctx: TenantContext, world: World
) -> None:
    body = client_as(ctx).get(f"{BASE}/exams/{world.exam2}/subjects/{world.science}").json()
    assert body["summary"]["overall"]["absent_count"] == 1
    assert body["summary"]["overall"]["mean_marks"] == "55.80"
    rows = {r["pseudo_id"]: r for r in body["students"]}
    assert rows["S-0004"]["is_absent"] is True and rows["S-0004"]["delta"] == "-40.00"
    assert rows["S-0001"]["marks"] == "85.00"


def test_at_risk_trend_teacher_overview_and_exams_endpoints(
    client_as: Callable[[TenantContext], TestClient], ctx: TenantContext, world: World
) -> None:
    c = client_as(ctx)
    risk = c.get(f"{BASE}/exams/{world.exam2}/at-risk").json()
    assert risk["count"] == 4
    first = risk["students"][0]
    assert first["pseudo_id"] == "S-0004" and first["severity"] == "high"
    assert [r["code"] for r in first["reasons"]] == [
        "FAILED_SUBJECTS",
        "SHARP_DROP",
        "LOW_OVERALL",
    ]

    trend = c.get(f"{BASE}/students/{world.students[2]}/trend").json()
    assert [p["result"]["percentage"] for p in trend["points"]] == ["88.00", "68.00"]
    assert trend["points"][1]["at_risk"]["reasons"][0]["code"] == "SHARP_DROP"

    teacher = c.get(f"{BASE}/teachers/{world.teacher}", params={"exam_id": world.exam2})
    assert teacher.status_code == 200, teacher.text
    assert len(teacher.json()["assignments"]) == 3
    assert c.get(f"{BASE}/teachers/{world.teacher}").status_code == 422  # exam_id required

    overview = c.get(f"{BASE}/overview").json()
    assert overview["latest_exam"]["id"] == world.exam2
    assert overview["summary"]["pass_percentage"] == "50.00"
    assert [t["pass_percentage"] for t in overview["trend"]] == ["100.00", "50.00"]

    exams = c.get(f"{BASE}/exams").json()
    assert [(e["exam"]["name"], e["has_marks"]) for e in exams] == [
        ("Unit Test 1", True),
        ("Unit Test 2", True),
        ("Term 1", False),
    ]


def test_cross_tenant_returns_404(
    client_as: Callable[[TenantContext], TestClient],
    make_tenant: Callable[..., TenantContext],
    world: World,
) -> None:
    other = client_as(make_tenant())
    urls = [
        f"{BASE}/exams/{world.exam2}/summary",
        f"{BASE}/exams/{world.exam2}/classes/{world.sec_a}",
        f"{BASE}/exams/{world.exam2}/subjects/{world.maths}",
        f"{BASE}/exams/{world.exam2}/at-risk",
        f"{BASE}/students/{world.students[1]}/trend",
        f"{BASE}/teachers/{world.teacher}?exam_id={world.exam2}",
    ]
    for url in urls:
        res = other.get(url)
        assert res.status_code == 404, url
        assert res.json()["error"]["code"] == "NOT_FOUND"
    overview = other.get(f"{BASE}/overview").json()
    assert overview["latest_exam"] is None and overview["student_count"] == 0
    assert other.get(f"{BASE}/exams").json() == []


def test_foreign_ids_mixed_into_own_requests_return_404(
    db: Session,
    client_as: Callable[[TenantContext], TestClient],
    make_tenant: Callable[..., TenantContext],
    ctx: TenantContext,
    world: World,
) -> None:
    other_ctx = make_tenant()
    foreign = build_world(db, other_ctx.school_id)
    c = client_as(ctx)
    assert (
        c.get(
            f"{BASE}/exams/{world.exam2}/summary",
            params={"class_section_ids": f"{world.sec_a},{foreign.sec_a}"},
        ).status_code
        == 404
    )
    assert c.get(f"{BASE}/exams/{world.exam2}/classes/{foreign.sec_a}").status_code == 404
    assert c.get(f"{BASE}/exams/{world.exam2}/subjects/{foreign.maths}").status_code == 404
    assert (
        c.get(f"{BASE}/teachers/{world.teacher}", params={"exam_id": foreign.exam2}).status_code
        == 404
    )


def test_unauthenticated_is_rejected(client: TestClient, world: World) -> None:
    assert client.get(f"{BASE}/exams/{world.exam2}/summary").status_code == 401
