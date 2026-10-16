"""Pure calculation tests against a hand-computed fixture (no database).

Fixture: 6 students in two sections (8-A: S1-S4, 8-B: S5-S6), 3 subjects, 2 exams.
Max total = 100 + 100 + 50 = 250, so percentage = total x 0.4.

Exam 2 (current)                         Exam 1 (previous)
     Maths Sci  Eng  total  %             Maths Sci Eng total  %      delta
S1   90    85   45   220   88.00          80   80  40  200   80.00   +8.00
S2   70    60   40   170   68.00          90   85  45  220   88.00  -20.00
S3   70    60   40   170   68.00          60   60  30  150   60.00   +8.00
S4   30    ABS  20    50   20.00          40   40  20  100   40.00  -20.00
S5   50    40   17   107   42.80          50   50  25  125   50.00   -7.20
S6   34.5  34   10    78.5 31.40          35   35  18   88   35.20   -3.80
Pass marks: Maths 35, Science 35, English 18 (of 50).
"""

from decimal import Decimal

from app.analytics.calculations import (
    AtRiskStudent,
    MarkRecord,
    StudentInfo,
    SubjectConfig,
    at_risk_students,
    class_summary,
    compare_exams,
    quantize,
    student_results,
    subject_summary,
)

D = Decimal
MATHS, SCIENCE, ENGLISH = 1, 2, 3
SEC_A, SEC_B = 10, 20

CONFIGS = [
    SubjectConfig(MATHS, "Maths", D("100"), D("35")),
    SubjectConfig(SCIENCE, "Science", D("100"), D("35")),
    SubjectConfig(ENGLISH, "English", D("50"), D("18")),
]

STUDENTS = [
    StudentInfo(1, "S-0001", "Asha", SEC_A, "8-A"),
    StudentInfo(2, "S-0002", "Bala", SEC_A, "8-A"),
    StudentInfo(3, "S-0003", "Chitra", SEC_A, "8-A"),
    StudentInfo(4, "S-0004", "Dev", SEC_A, "8-A"),
    StudentInfo(5, "S-0005", "Esha", SEC_B, "8-B"),
    StudentInfo(6, "S-0006", "Farid", SEC_B, "8-B"),
]

ABSENT = "ABS"


def _marks(table: dict[int, tuple[str, str, str]]) -> list[MarkRecord]:
    records: list[MarkRecord] = []
    for sid, values in table.items():
        for subject_id, value in zip((MATHS, SCIENCE, ENGLISH), values, strict=True):
            if value == ABSENT:
                records.append(MarkRecord(sid, subject_id, None, is_absent=True))
            else:
                records.append(MarkRecord(sid, subject_id, D(value)))
    return records


CURRENT = _marks(
    {
        1: ("90", "85", "45"),
        2: ("70", "60", "40"),
        3: ("70", "60", "40"),
        4: ("30", ABSENT, "20"),
        5: ("50", "40", "17"),
        6: ("34.5", "34", "10"),
    }
)
PREVIOUS = _marks(
    {
        1: ("80", "80", "40"),
        2: ("90", "85", "45"),
        3: ("60", "60", "30"),
        4: ("40", "40", "20"),
        5: ("50", "50", "25"),
        6: ("35", "35", "18"),
    }
)


def _by_id(results: list) -> dict:  # type: ignore[type-arg]
    return {r.student_id: r for r in results}


def test_student_totals_percentages_and_pass_flags() -> None:
    res = _by_id(student_results(STUDENTS, CONFIGS, CURRENT))
    expected = {
        1: ("220.00", "88.00", True, []),
        2: ("170.00", "68.00", True, []),
        3: ("170.00", "68.00", True, []),
        4: ("50.00", "20.00", False, [MATHS, SCIENCE]),
        5: ("107.00", "42.80", False, [ENGLISH]),
        6: ("78.50", "31.40", False, [MATHS, SCIENCE, ENGLISH]),
    }
    for sid, (total, pct, passed, failed) in expected.items():
        r = res[sid]
        assert r.total == D(total), sid
        assert r.percentage == D(pct), sid
        assert r.passed is passed, sid
        assert r.failed_subjects == failed, sid
        assert r.max_total == D("250.00")
    s4_science = res[4].subject(SCIENCE)
    assert s4_science is not None
    assert s4_science.is_absent and not s4_science.passed and s4_science.marks is None
    assert s4_science.percentage == D("0.00")
    assert res[5].subject(ENGLISH).percentage == D("34.00")  # 17/50


def test_rank_within_section_uses_competition_ranking() -> None:
    results = student_results(STUDENTS, CONFIGS, CURRENT)
    res = _by_id(results)
    assert [res[i].rank_in_section for i in (1, 2, 3, 4)] == [1, 2, 2, 4]
    assert [res[i].rank_in_section for i in (5, 6)] == [1, 2]
    assert res[1].section_size == 4 and res[5].section_size == 2
    # Output ordered by section then rank then pseudo id
    assert [r.student_id for r in results] == [1, 2, 3, 4, 5, 6]


def test_class_summary_school_and_sections() -> None:
    results = student_results(STUDENTS, CONFIGS, CURRENT)
    school = class_summary(results)
    assert school.student_count == 6
    assert school.appeared_count == 6
    assert school.pass_count == 3 and school.fail_count == 3
    assert school.pass_percentage == D("50.00")
    assert school.mean_percentage == D("53.03")  # 318.2 / 6
    assert school.median_percentage == D("55.40")  # (42.8 + 68) / 2
    assert school.highest_percentage == D("88.00")
    assert school.lowest_percentage == D("20.00")
    assert [(b.label, b.count) for b in school.distribution] == [
        ("0-35", 2),
        ("35-50", 1),
        ("50-75", 2),
        ("75-90", 1),
        ("90-100", 0),
    ]

    sec_a = class_summary([r for r in results if r.class_section_id == SEC_A], SEC_A, "8-A")
    assert sec_a.pass_percentage == D("75.00")
    assert sec_a.mean_percentage == D("61.00")
    assert sec_a.median_percentage == D("68.00")
    sec_b = class_summary([r for r in results if r.class_section_id == SEC_B], SEC_B, "8-B")
    assert sec_b.pass_percentage == D("0.00")
    assert sec_b.mean_percentage == D("37.10")
    assert sec_b.median_percentage == D("37.10")


def test_distribution_band_boundaries() -> None:
    configs = [SubjectConfig(1, "Only", D("100"), D("35"))]
    students = [StudentInfo(i, f"S-{i}", f"N{i}", 1, "1-A") for i in range(1, 8)]
    values = ["0", "34.99", "35", "50", "75", "90", "100"]
    marks = [MarkRecord(i, 1, D(v)) for i, v in zip(range(1, 8), values, strict=True)]
    summary = class_summary(student_results(students, configs, marks))
    assert [b.count for b in summary.distribution] == [2, 1, 1, 1, 2]


def test_subject_summary_per_section_and_change() -> None:
    curr = student_results(STUDENTS, CONFIGS, CURRENT)
    prev = student_results(STUDENTS, CONFIGS, PREVIOUS)
    prev_summary = subject_summary(prev, CONFIGS)
    summaries = {s.subject_id: s for s in subject_summary(curr, CONFIGS, prev_summary)}

    maths = summaries[MATHS]
    assert maths.overall.pass_count == 4
    assert maths.overall.pass_percentage == D("66.67")
    assert maths.overall.mean_marks == D("57.42")  # 344.5 / 6
    assert maths.overall.highest_marks == D("90.00")
    assert maths.overall.lowest_marks == D("30.00")
    assert maths.overall.absent_count == 0
    assert {s.class_section_id: s.stats.pass_percentage for s in maths.sections} == {
        SEC_A: D("75.00"),
        SEC_B: D("50.00"),
    }
    assert maths.weakest_sections == [SEC_B]
    assert maths.mean_percentage_change == D("-1.75")  # 57.42 - 59.17

    science = summaries[SCIENCE]
    assert science.overall.absent_count == 1
    assert science.overall.appeared_count == 5
    assert science.overall.pass_percentage == D("66.67")
    assert science.overall.mean_marks == D("55.80")  # 279 / 5 (absent excluded)

    english = summaries[ENGLISH]
    assert english.overall.mean_marks == D("28.67")
    assert english.overall.mean_percentage == D("57.33")
    assert {s.class_section_id: s.stats.pass_percentage for s in english.sections} == {
        SEC_A: D("100.00"),
        SEC_B: D("0.00"),
    }


def test_compare_exams_deltas() -> None:
    curr = student_results(STUDENTS, CONFIGS, CURRENT)
    prev = student_results(STUDENTS, CONFIGS, PREVIOUS)
    changes = {c.student_id: c for c in compare_exams(prev, curr)}
    assert {sid: c.delta for sid, c in changes.items()} == {
        1: D("8.00"),
        2: D("-20.00"),
        3: D("8.00"),
        4: D("-20.00"),
        5: D("-7.20"),
        6: D("-3.80"),
    }
    s2 = {s.subject_id: s.delta for s in changes[2].subjects}
    assert s2 == {MATHS: D("-20.00"), SCIENCE: D("-25.00"), ENGLISH: D("-10.00")}
    s4 = {s.subject_id: s.delta for s in changes[4].subjects}
    assert s4[SCIENCE] == D("-40.00")  # absent counts as 0


def test_at_risk_rule_reasons_and_severity() -> None:
    curr = student_results(STUDENTS, CONFIGS, CURRENT)
    prev = student_results(STUDENTS, CONFIGS, PREVIOUS)
    flagged = at_risk_students(curr, compare_exams(prev, curr))

    assert [a.student_id for a in flagged] == [4, 6, 5, 2]
    by_id: dict[int, AtRiskStudent] = {a.student_id: a for a in flagged}
    assert [r.code for r in by_id[4].reasons] == ["FAILED_SUBJECTS", "SHARP_DROP", "LOW_OVERALL"]
    assert by_id[4].severity == "high"
    assert by_id[4].reasons[0].evidence["count"] == 2
    assert by_id[4].reasons[0].evidence["subjects"][1]["is_absent"] is True
    assert by_id[4].reasons[1].evidence["delta"] == "-20.00"

    assert [r.code for r in by_id[6].reasons] == ["FAILED_SUBJECTS", "LOW_OVERALL"]
    assert by_id[6].severity == "high"
    assert by_id[6].failed_subject_count == 3

    assert [r.code for r in by_id[5].reasons] == ["FAILED_SUBJECTS"]
    assert by_id[5].severity == "medium"
    assert by_id[5].reasons[0].detail == "Failed 1 subject: English"

    assert [r.code for r in by_id[2].reasons] == ["SHARP_DROP"]
    assert by_id[2].severity == "medium"
    assert by_id[2].delta == D("-20.00")
    assert 1 not in by_id and 3 not in by_id


def test_three_failed_subjects_alone_is_high_severity() -> None:
    configs = [SubjectConfig(i, f"Sub{i}", D("100"), D("35")) for i in (1, 2, 3, 4)]
    student = [StudentInfo(1, "S-1", "One", 1, "1-A")]
    marks = [MarkRecord(1, i, D(v)) for i, v in ((1, "30"), (2, "30"), (3, "30"), (4, "100"))]
    flagged = at_risk_students(student_results(student, configs, marks))
    assert [r.code for r in flagged[0].reasons] == ["FAILED_SUBJECTS"]  # 47.5% >= 40
    assert flagged[0].severity == "high"


def test_drop_threshold_is_inclusive_and_no_previous_exam() -> None:
    configs = [SubjectConfig(1, "Only", D("100"), D("35"))]
    student = [StudentInfo(1, "S-1", "One", 1, "1-A")]
    prev = student_results(student, configs, [MarkRecord(1, 1, D("75"))])
    curr = student_results(student, configs, [MarkRecord(1, 1, D("60"))])
    flagged = at_risk_students(curr, compare_exams(prev, curr))
    assert [r.code for r in flagged[0].reasons] == ["SHARP_DROP"]  # exactly -15
    assert at_risk_students(curr, None) == []  # no previous exam -> no drop reason
    curr2 = student_results(student, configs, [MarkRecord(1, 1, D("60.01"))])
    assert at_risk_students(curr2, compare_exams(prev, curr2)) == []


def test_all_absent_and_missing_marks() -> None:
    results = student_results(
        STUDENTS[:2],
        CONFIGS,
        [MarkRecord(1, s, None, is_absent=True) for s in (MATHS, SCIENCE, ENGLISH)],
    )
    for r in results:
        assert r.percentage == D("0.00") and not r.passed and not r.appeared
        assert r.failed_subjects == [MATHS, SCIENCE, ENGLISH]
    assert results[1].subjects[0].is_missing  # student 2 has no records at all
    assert [r.rank_in_section for r in results] == [1, 1]
    summary = class_summary(results)
    assert summary.student_count == 2 and summary.appeared_count == 0
    assert summary.pass_percentage == D("0.00")
    assert summary.mean_percentage is None and summary.median_percentage is None
    assert all(b.count == 0 for b in summary.distribution)
    subj = subject_summary(results, CONFIGS)[0]
    assert subj.overall.absent_count == 1 and subj.overall.missing_count == 1
    assert subj.overall.mean_marks is None
    flagged = at_risk_students(results)
    assert all(a.severity == "high" for a in flagged)


def test_empty_inputs() -> None:
    summary = class_summary([])
    assert summary.student_count == 0 and summary.pass_percentage is None
    assert student_results([], CONFIGS, []) == []
    assert subject_summary([], CONFIGS)[0].overall.pass_percentage is None
    no_config = student_results(STUDENTS[:1], [], [])
    assert no_config[0].passed is False and no_config[0].percentage == D("0.00")


def test_rounding_is_half_up() -> None:
    assert quantize(D("25.025")) == D("25.03")
    configs = [SubjectConfig(1, "Only", D("80"), D("20"))]
    student = [StudentInfo(1, "S-1", "One", 1, "1-A")]
    result = student_results(student, configs, [MarkRecord(1, 1, D("20.02"))])[0]
    assert result.percentage == D("25.03")  # 25.025 -> half-up (half-even would give 25.02)


def test_to_dict_is_json_serializable() -> None:
    import json

    curr = student_results(STUDENTS, CONFIGS, CURRENT)
    prev = student_results(STUDENTS, CONFIGS, PREVIOUS)
    flagged = at_risk_students(curr, compare_exams(prev, curr))
    payload = {
        "results": [r.to_dict() for r in curr],
        "summary": class_summary(curr).to_dict(),
        "at_risk": [a.to_dict() for a in flagged],
    }
    text = json.dumps(payload)
    assert '"percentage": "88.00"' in text
    assert payload["summary"]["mean_percentage"] == "53.03"
    assert payload["at_risk"][0]["reasons"][0]["code"] == "FAILED_SUBJECTS"
