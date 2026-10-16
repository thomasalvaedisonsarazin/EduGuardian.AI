"""Pure, deterministic generators for the demo dataset (no database access).

Everything is driven by an explicit ``random.Random`` so the same seed yields the same data.

Shape of the generated marks:
- ~15% of students are "struggling" (low ability) and fail at least one subject.
- A few students per section are "droppers": they fall >15 points between exam 1 and 2.
- One subject is weak in one section (default: Mathematics in 10-B).
- A small number of (student, subject, exam) entries are absences (marks = None).
"""

import csv
import io
import random
from collections.abc import Sequence
from dataclasses import dataclass

SUBJECTS: tuple[tuple[str, str], ...] = (
    ("English", "ENG"),
    ("Mathematics", "MATH"),
    ("Science", "SCI"),
    ("Social Science", "SST"),
    ("Hindi", "HIN"),
)
SECTIONS: tuple[str, ...] = ("A", "B")
STUDENTS_PER_SECTION = 40
GRADE = 10
EXAMS: tuple[tuple[str, int], ...] = (("Unit Test 1", 1), ("Quarterly Exam", 2))
SUBJECT_NAMES: tuple[str, ...] = tuple(name for name, _code in SUBJECTS)
EXAM_SEQUENCES: tuple[int, ...] = tuple(seq for _name, seq in EXAMS)
MAX_MARKS = 100
PASS_MARKS = 35
WEAK_SECTION = "B"
WEAK_SUBJECT = "Mathematics"

STRUGGLING_RATE = 0.15
DROPPERS_PER_SECTION = 3
ABSENCE_RATE = 0.012

# Small fallback pool when Faker is not installed (it is a dev dependency).
_FIRST_NAMES = (
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna",
    "Ishaan", "Rohan", "Kabir", "Ananya", "Diya", "Aadhya", "Saanvi", "Pari", "Anika", "Navya",
    "Myra", "Ira", "Kiara", "Meera", "Riya", "Tanvi", "Nikhil", "Pranav", "Harsh", "Kavya",
    "Sneha", "Priya", "Neha", "Rahul", "Siddharth", "Aisha", "Zoya", "Farhan", "Gurpreet",
)  # fmt: skip
_LAST_NAMES = (
    "Sharma", "Verma", "Gupta", "Patel", "Reddy", "Iyer", "Nair", "Singh", "Kumar", "Das",
    "Mehta", "Joshi", "Chopra", "Bose", "Banerjee", "Mukherjee", "Rao", "Pillai", "Kapoor",
    "Malhotra", "Agarwal", "Bhat", "Khan", "Sethi", "Menon", "Kulkarni", "Desai", "Saxena",
)  # fmt: skip


@dataclass(frozen=True)
class StudentProfile:
    index: int  # 1-based, unique across the school
    section: str
    admission_no: str
    full_name: str
    ability: float
    struggling: bool
    dropper: bool


@dataclass(frozen=True)
class MarkRow:
    admission_no: str
    section: str
    subject: str
    exam_sequence: int
    marks: int | None
    is_absent: bool


def admission_number(index: int) -> str:
    return f"GPS{1000 + index}"


def generate_student_names(count: int, seed: int = 42) -> list[str]:
    """``count`` unique Indian-style names (Faker en_IN when available)."""
    names: list[str] = []
    seen: set[str] = set()
    try:
        from faker import Faker

        fake = Faker("en_IN")
        fake.seed_instance(seed)
        attempts = 0
        while len(names) < count and attempts < count * 50:
            attempts += 1
            name = f"{fake.first_name()} {fake.last_name()}"
            if name not in seen:
                seen.add(name)
                names.append(name)
    except ImportError:
        pass
    rng = random.Random(seed)
    while len(names) < count:
        name = f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def build_profiles(
    rng: random.Random,
    names: Sequence[str],
    sections: Sequence[str] = SECTIONS,
    per_section: int = STUDENTS_PER_SECTION,
) -> list[StudentProfile]:
    """Assign each student a section, admission number, latent ability and risk flags."""
    if len(names) < len(sections) * per_section:
        raise ValueError("not enough names for the requested number of students")
    profiles: list[StudentProfile] = []
    index = 0
    for section in sections:
        n_struggling = round(per_section * STRUGGLING_RATE)
        positions = list(range(per_section))
        struggling = set(rng.sample(positions, n_struggling))
        healthy = [p for p in positions if p not in struggling]
        droppers = set(rng.sample(healthy, min(DROPPERS_PER_SECTION, len(healthy))))
        for pos in positions:
            index += 1
            is_struggling = pos in struggling
            ability = rng.gauss(38, 4) if is_struggling else rng.gauss(70, 9)
            profiles.append(
                StudentProfile(
                    index=index,
                    section=section,
                    admission_no=admission_number(index),
                    full_name=names[index - 1],
                    ability=max(25.0, min(95.0, ability)),
                    struggling=is_struggling,
                    dropper=pos in droppers,
                )
            )
    return profiles


def generate_marks(
    rng: random.Random,
    profiles: Sequence[StudentProfile],
    subjects: Sequence[str] = SUBJECT_NAMES,
    exam_sequences: Sequence[int] = EXAM_SEQUENCES,
    weak: tuple[str, str] = (WEAK_SECTION, WEAK_SUBJECT),
    max_marks: int = MAX_MARKS,
) -> list[MarkRow]:
    """One row per (exam, student, subject); deterministic for a given ``rng`` state."""
    subject_offset = {s: rng.uniform(-3, 3) for s in subjects}
    first_seq = min(exam_sequences)
    rows: list[MarkRow] = []
    for seq in exam_sequences:
        for p in profiles:
            drop = rng.uniform(18, 26) if p.dropper and seq != first_seq else 0.0
            for subject in subjects:
                if rng.random() < ABSENCE_RATE:
                    rows.append(MarkRow(p.admission_no, p.section, subject, seq, None, True))
                    continue
                score = p.ability + subject_offset[subject] + rng.gauss(0, 5) - drop
                if (p.section, subject) == weak:
                    score -= 14
                if p.struggling:
                    # Make sure every struggling student fails at least their weakest subject.
                    score = min(score, p.ability + 2)
                marks = int(round(max(0.0, min(float(max_marks), score))))
                rows.append(MarkRow(p.admission_no, p.section, subject, seq, marks, False))
    _guarantee_struggling_fail(rows, profiles, subjects, max(exam_sequences))
    return rows


def _guarantee_struggling_fail(
    rows: list[MarkRow],
    profiles: Sequence[StudentProfile],
    subjects: Sequence[str],
    exam_seq: int,
) -> None:
    """In the latest exam, force each struggling student's lowest mark below the pass line."""
    by_key = {(r.admission_no, r.subject, r.exam_sequence): i for i, r in enumerate(rows)}
    for p in profiles:
        if not p.struggling:
            continue
        idxs = [by_key[(p.admission_no, s, exam_seq)] for s in subjects]
        present = [i for i in idxs if rows[i].marks is not None]
        if not present:
            continue
        lowest = min(present, key=lambda i: rows[i].marks or 0)
        row = rows[lowest]
        if row.marks is not None and row.marks >= PASS_MARKS:
            rows[lowest] = MarkRow(
                row.admission_no, row.section, row.subject, row.exam_sequence, PASS_MARKS - 4, False
            )


# --- sample CSVs for the marks-import demo ----------------------------------------------------
def build_sample_marks_csv(
    rows: Sequence[MarkRow], section: str, exam_sequence: int, subjects: Sequence[str]
) -> str:
    """CSV with ``admission_no`` + one column per subject; absences written as ``AB``."""
    table: dict[str, dict[str, str]] = {}
    for r in rows:
        if r.section != section or r.exam_sequence != exam_sequence:
            continue
        table.setdefault(r.admission_no, {})[r.subject] = "AB" if r.is_absent else str(r.marks)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["admission_no", *subjects])
    for adm in sorted(table):
        writer.writerow([adm, *(table[adm].get(s, "") for s in subjects)])
    return buf.getvalue()


def build_sample_marks_with_errors_csv(clean_csv: str) -> str:
    """Copy of ``clean_csv`` with deliberate problems for the Data Quality demo.

    - row 1: first subject mark set to 105 (exceeds max)
    - row 2: second subject marked ``AB`` (absent)
    - row 3: third subject left blank (missing)
    - extra row with an unknown admission number (``GPS9999``)
    """
    reader = list(csv.reader(io.StringIO(clean_csv)))
    header, body = reader[0], [list(r) for r in reader[1:]]
    if len(body) >= 3 and len(header) >= 4:
        body[0][1] = "105"
        body[1][2] = "AB"
        body[2][3] = ""
    unknown = ["GPS9999", *(["60"] * (len(header) - 1))]
    body.append(unknown)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(body)
    return buf.getvalue()
