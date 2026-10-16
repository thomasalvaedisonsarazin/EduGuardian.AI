"""Persist the demo school ("Greenfield Public School", code GPS) using the pure generators."""

import logging
import random
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

import bcrypt
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import (
    AcademicYear,
    Base,
    ClassSection,
    Exam,
    ExamSubjectConfig,
    Mark,
    Membership,
    MembershipRole,
    School,
    Student,
    Subject,
    Teacher,
    TeachingAssignment,
    User,
)
from app.seed import generator as gen
from app.services.setup_service import format_pseudo_id

logger = logging.getLogger(__name__)

SCHOOL_NAME = "Greenfield Public School"
SCHOOL_CODE = "GPS"
DEFAULT_ADMIN_EMAIL = "demo@eduguardian.test"
DEFAULT_PASSWORD = "Demo@12345"
TEACHER_EMAIL = "teacher@eduguardian.test"
ACADEMIC_YEAR = "2026-27"
SEED = 42
SAMPLE_DIR = Path(__file__).resolve().parent
SAMPLE_CLEAN = "sample_marks_quarterly_10A.csv"
SAMPLE_ERRORS = "sample_marks_with_errors.csv"

# (teacher name, subject taught, class-teacher-of section or None, linked to teacher login?)
TEACHERS: tuple[tuple[str, str, str | None, bool], ...] = (
    ("Meenakshi Iyer", "English", "A", False),
    ("Rajesh Kumar", "Mathematics", "B", True),
    ("Anita Desai", "Science", None, False),
    ("Suresh Menon", "Social Science", None, False),
    ("Kavita Sharma", "Hindi", None, False),
)
EXAM_DATES = {1: date(2026, 7, 20), 2: date(2026, 9, 21)}


@dataclass
class SeedSummary:
    school_id: int
    created: bool
    counts: dict[str, int] = field(default_factory=dict)
    sample_files: list[str] = field(default_factory=list)


def hash_password(password: str) -> str:
    """Same scheme as Module 1 auth."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _get_or_create_user(db: Session, email: str, full_name: str, password: str) -> User:
    user = db.scalars(select(User).where(func.lower(User.email) == email.lower())).first()
    if user is None:
        user = User(
            email=email.lower(), full_name=full_name, hashed_password=hash_password(password)
        )
        db.add(user)
    else:
        logger.info("Reusing existing user %s (password reset to the seed password)", email)
        user.hashed_password = hash_password(password)
        user.is_active = True
    db.flush()
    return user


def find_demo_school(db: Session) -> School | None:
    return db.scalars(select(School).where(School.code == SCHOOL_CODE)).first()


def reset_demo(db: Session, emails: tuple[str, ...]) -> None:
    """Delete the GPS school (DB cascades remove its data) and orphaned demo users."""
    school = find_demo_school(db)
    if school is not None:
        db.execute(delete(School).where(School.id == school.id))
        logger.info("Deleted demo school id=%s", school.id)
    for email in emails:
        user = db.scalars(select(User).where(func.lower(User.email) == email.lower())).first()
        if user is None:
            continue
        has_other = db.scalar(
            select(func.count(Membership.id)).where(Membership.user_id == user.id)
        )
        if not has_other:
            db.execute(delete(User).where(User.id == user.id))
    db.flush()
    db.expire_all()


def count_school(db: Session, school_id: int) -> dict[str, int]:
    models: dict[str, type[Base]] = {
        "academic_years": AcademicYear,
        "classes": ClassSection,
        "subjects": Subject,
        "teachers": Teacher,
        "teaching_assignments": TeachingAssignment,
        "students": Student,
        "exams": Exam,
        "exam_subject_configs": ExamSubjectConfig,
        "marks": Mark,
    }
    counts: dict[str, int] = {}
    for key, model in models.items():
        table = model.__table__
        stmt = select(func.count()).select_from(table).where(table.c.school_id == school_id)
        counts[key] = int(db.scalar(stmt) or 0)
    return counts


def seed_demo(
    db: Session,
    *,
    email: str = DEFAULT_ADMIN_EMAIL,
    password: str = DEFAULT_PASSWORD,
    reset: bool = False,
    sample_dir: Path | None = SAMPLE_DIR,
    commit: bool = True,
) -> SeedSummary:
    """Create the demo school. Idempotent: if GPS exists and ``reset`` is False, do nothing."""
    if reset:
        reset_demo(db, (email, TEACHER_EMAIL))
    existing = find_demo_school(db)
    if existing is not None:
        logger.info("Demo school already exists (id=%s); use --reset to recreate", existing.id)
        return SeedSummary(existing.id, created=False, counts=count_school(db, existing.id))

    rng = random.Random(SEED)
    subject_names = [name for name, _ in gen.SUBJECTS]

    school = School(name=SCHOOL_NAME, code=SCHOOL_CODE)
    db.add(school)
    db.flush()
    sid = school.id

    admin = _get_or_create_user(db, email, "Demo Admin", password)
    teacher_user = _get_or_create_user(db, TEACHER_EMAIL, "Rajesh Kumar", password)
    db.add_all(
        [
            Membership(user_id=admin.id, school_id=sid, role=MembershipRole.school_admin),
            Membership(user_id=teacher_user.id, school_id=sid, role=MembershipRole.teacher),
        ]
    )

    year = AcademicYear(school_id=sid, label=ACADEMIC_YEAR, is_current=True)
    db.add(year)
    db.flush()

    classes = {
        s: ClassSection(school_id=sid, academic_year_id=year.id, grade=gen.GRADE, section=s)
        for s in gen.SECTIONS
    }
    subjects = {name: Subject(school_id=sid, name=name, code=code) for name, code in gen.SUBJECTS}
    db.add_all([*classes.values(), *subjects.values()])
    db.flush()

    for name, subject_name, class_teacher_of, linked in TEACHERS:
        teacher = Teacher(
            school_id=sid, full_name=name, user_id=teacher_user.id if linked else None
        )
        db.add(teacher)
        db.flush()
        for section, cs in classes.items():
            db.add(
                TeachingAssignment(
                    school_id=sid,
                    teacher_id=teacher.id,
                    class_section_id=cs.id,
                    subject_id=subjects[subject_name].id,
                    is_class_teacher=class_teacher_of == section,
                )
            )

    names = gen.generate_student_names(len(gen.SECTIONS) * gen.STUDENTS_PER_SECTION, SEED)
    profiles = gen.build_profiles(rng, names)
    students: dict[str, Student] = {}
    for p in profiles:
        st = Student(
            school_id=sid,
            class_section_id=classes[p.section].id,
            admission_no=p.admission_no,
            full_name=p.full_name,
            pseudo_id=format_pseudo_id(p.index),
        )
        students[p.admission_no] = st
    db.add_all(students.values())

    exams: dict[int, Exam] = {}
    for exam_name, seq in gen.EXAMS:
        exam = Exam(
            school_id=sid,
            academic_year_id=year.id,
            name=exam_name,
            sequence=seq,
            held_on=EXAM_DATES.get(seq),
        )
        exams[seq] = exam
    db.add_all(exams.values())
    db.flush()
    for exam in exams.values():
        for subj in subjects.values():
            db.add(
                ExamSubjectConfig(
                    school_id=sid,
                    exam_id=exam.id,
                    subject_id=subj.id,
                    max_marks=Decimal(gen.MAX_MARKS),
                    pass_marks=Decimal(gen.PASS_MARKS),
                )
            )

    rows = gen.generate_marks(rng, profiles, subject_names)
    db.add_all(
        Mark(
            school_id=sid,
            exam_id=exams[r.exam_sequence].id,
            student_id=students[r.admission_no].id,
            subject_id=subjects[r.subject].id,
            marks_obtained=Decimal(r.marks) if r.marks is not None else None,
            is_absent=r.is_absent,
        )
        for r in rows
    )
    db.flush()

    summary = SeedSummary(sid, created=True, counts=count_school(db, sid))
    if sample_dir is not None:
        summary.sample_files = write_sample_files(rows, subject_names, sample_dir)
    if commit:
        db.commit()
    logger.info("Seeded demo school id=%s: %s", sid, summary.counts)
    return summary


def write_sample_files(
    rows: list[gen.MarkRow], subject_names: list[str], directory: Path
) -> list[str]:
    quarterly_seq = max(seq for _, seq in gen.EXAMS)
    clean = gen.build_sample_marks_csv(rows, "A", quarterly_seq, subject_names)
    with_errors = gen.build_sample_marks_with_errors_csv(clean)
    directory.mkdir(parents=True, exist_ok=True)
    paths = [directory / SAMPLE_CLEAN, directory / SAMPLE_ERRORS]
    paths[0].write_text(clean, encoding="utf-8", newline="")
    paths[1].write_text(with_errors, encoding="utf-8", newline="")
    return [str(p) for p in paths]
