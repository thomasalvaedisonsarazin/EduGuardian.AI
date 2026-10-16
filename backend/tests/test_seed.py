"""Seed generator (pure) and persistence tests."""

import csv
import io
import random
from collections import defaultdict
from pathlib import Path

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Mark, Membership, School, Student, Subject, TeachingAssignment, User
from app.seed import generator as gen
from app.seed.demo import (
    DEFAULT_ADMIN_EMAIL,
    SAMPLE_CLEAN,
    SAMPLE_ERRORS,
    SCHOOL_CODE,
    seed_demo,
)


def _generate() -> tuple[list[gen.StudentProfile], list[gen.MarkRow]]:
    rng = random.Random(42)
    names = gen.generate_student_names(80, 42)
    profiles = gen.build_profiles(rng, names)
    return profiles, gen.generate_marks(rng, profiles)


def test_generator_is_deterministic() -> None:
    assert _generate() == _generate()


def test_generator_distribution() -> None:
    profiles, rows = _generate()
    assert len(profiles) == 80 and len({p.full_name for p in profiles}) == 80
    assert len(rows) == 80 * 5 * 2
    by: dict[tuple[str, int], dict[str, int | None]] = defaultdict(dict)
    for r in rows:
        by[(r.admission_no, r.exam_sequence)][r.subject] = r.marks
        assert (r.marks is None) == r.is_absent
        assert r.marks is None or 0 <= r.marks <= 100

    failing = [
        p
        for p in profiles
        if any(m is not None and m < gen.PASS_MARKS for m in by[(p.admission_no, 2)].values())
    ]
    assert 0.10 <= len(failing) / len(profiles) <= 0.25

    def avg(d: dict[str, int | None]) -> float:
        vals = [v for v in d.values() if v is not None]
        return sum(vals) / len(vals)

    droppers = [
        p for p in profiles if avg(by[(p.admission_no, 1)]) - avg(by[(p.admission_no, 2)]) > 15
    ]
    assert len(droppers) >= 4

    def subject_mean(section: str, subject: str) -> float:
        vals = [
            r.marks
            for r in rows
            if r.section == section and r.subject == subject and r.marks is not None
        ]
        return sum(vals) / len(vals)

    assert subject_mean("B", "Mathematics") < subject_mean("A", "Mathematics") - 8
    assert 1 <= sum(r.is_absent for r in rows) <= 30


def test_sample_csvs() -> None:
    _, rows = _generate()
    clean = gen.build_sample_marks_csv(rows, "A", 2, gen.SUBJECT_NAMES)
    parsed = list(csv.reader(io.StringIO(clean)))
    assert parsed[0] == ["admission_no", *gen.SUBJECT_NAMES]
    assert len(parsed) == 41
    errors = list(csv.reader(io.StringIO(gen.build_sample_marks_with_errors_csv(clean))))
    flat = [c for row in errors[1:] for c in row]
    assert "105" in flat and "AB" in flat and "" in flat
    assert errors[-1][0] == "GPS9999"


def test_seed_demo_creates_and_is_idempotent(db: Session, tmp_path: Path) -> None:
    summary = seed_demo(db, password="Secret@123", sample_dir=tmp_path)
    assert summary.created
    assert summary.counts == {
        "academic_years": 1,
        "classes": 2,
        "subjects": 5,
        "teachers": 5,
        "teaching_assignments": 10,
        "students": 80,
        "exams": 2,
        "exam_subject_configs": 10,
        "marks": 800,
    }
    assert (tmp_path / SAMPLE_CLEAN).exists() and (tmp_path / SAMPLE_ERRORS).exists()

    school = db.scalars(select(School).where(School.code == SCHOOL_CODE)).one()
    admin = db.scalars(select(User).where(User.email == DEFAULT_ADMIN_EMAIL)).one()
    assert bcrypt.checkpw(b"Secret@123", admin.hashed_password.encode())
    roles = {
        m.role.value
        for m in db.scalars(select(Membership).where(Membership.school_id == school.id))
    }
    assert roles == {"school_admin", "teacher"}
    class_teachers = db.scalar(
        select(func.count(TeachingAssignment.id)).where(
            TeachingAssignment.school_id == school.id, TeachingAssignment.is_class_teacher
        )
    )
    assert class_teachers == 2
    pseudo = sorted(db.scalars(select(Student.pseudo_id).where(Student.school_id == school.id)))
    assert pseudo[0] == "S-0001" and pseudo[-1] == "S-0080"
    absent = db.scalar(
        select(func.count(Mark.id)).where(Mark.is_absent, Mark.school_id == school.id)
    )
    assert absent and absent > 0
    assert {s.name for s in db.scalars(select(Subject).where(Subject.school_id == school.id))} == {
        "English",
        "Mathematics",
        "Science",
        "Social Science",
        "Hindi",
    }

    again = seed_demo(db, sample_dir=None)
    assert not again.created and again.school_id == school.id
    assert again.counts["marks"] == 800

    reset = seed_demo(db, reset=True, sample_dir=None)
    assert reset.created and reset.school_id != school.id
    assert db.scalar(select(func.count(School.id)).where(School.code == SCHOOL_CODE)) == 1
    assert db.scalar(select(func.count(Student.id)).where(Student.school_id == school.id)) == 0
