"""Unit tests for the pure Data Quality Agent functions (no DB)."""

import io
from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.agents import data_quality as dq
from app.exceptions import DomainValidationError

FIXTURES = Path(__file__).parent / "fixtures"

SUBJECTS = [
    dq.SubjectRef(id=1, name="Mathematics", code="MATH"),
    dq.SubjectRef(id=2, name="Science", code="SCI"),
    dq.SubjectRef(id=3, name="English", code="ENG"),
]
CONFIGS = {
    1: dq.SubjectLimits(Decimal("100"), Decimal("35")),
    2: (Decimal("50"), Decimal("18")),
    3: dq.SubjectLimits(Decimal("100"), Decimal("35")),
}
ROSTER = {
    "A001": dq.StudentRef(id=11, admission_no="A001", class_section_id=1),
    "A002": dq.StudentRef(id=12, admission_no="A002", class_section_id=1),
    "A003": dq.StudentRef(id=13, admission_no="A003", class_section_id=1),
    "A004": dq.StudentRef(id=14, admission_no="A004", class_section_id=1),
    "B001": dq.StudentRef(id=21, admission_no="B001", class_section_id=2),
}


def full_map() -> dq.ColumnMap:
    return dq.ColumnMap(admission_column="adm", subjects={"maths": 1, "sci": 2, "eng": 3})


def sheet(*rows: list[str], headers: list[str] | None = None) -> dq.ParsedSheet:
    return dq.ParsedSheet(headers=headers or ["adm", "maths", "sci", "eng"], rows=[*rows])


def codes(result: dq.ValidationResult) -> list[str]:
    return [i.code for i in result.issues]


def xlsx_bytes(rows: list[list[object]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# --- parsing -------------------------------------------------------------------------------
def test_parse_csv_fixture_strips_headers_and_reads_strings() -> None:
    parsed = dq.parse_marks_file((FIXTURES / "marks_sample.csv").read_bytes(), "marks.CSV")
    assert parsed.headers == ["Adm No", "Student Name", "Mathematics", "SCI", "English (100)"]
    assert parsed.rows[0] == ["A001", "Asha", "78", "AB", "91"]
    assert parsed.rows[1][4] == ""  # blank cell stays an empty string


def test_parse_csv_bom_and_blank_rows() -> None:
    content = "﻿ admission_no , Maths \nA001,5\n,\n".encode()
    parsed = dq.parse_marks_file(content, "x.csv")
    assert parsed.headers == ["admission_no", "Maths"]
    assert parsed.rows == [["A001", "5"]]


def test_parse_xlsx_numbers_become_strings() -> None:
    content = xlsx_bytes([["Admission No", "Maths"], [101, 45], [102, 67.5], [103, None]])
    parsed = dq.parse_marks_file(content, "marks.xlsx")
    assert parsed.headers == ["Admission No", "Maths"]
    assert [r[0] for r in parsed.rows] == ["101", "102", "103"]
    assert parsed.rows[0][1] == "45"
    assert parsed.rows[1][1] == "67.5"
    assert parsed.rows[2][1] == ""


def test_parse_rejects_bad_extension_empty_and_garbage() -> None:
    with pytest.raises(DomainValidationError) as exc:
        dq.parse_marks_file(b"a,b\n1,2", "marks.pdf")
    assert exc.value.code == "UNSUPPORTED_FILE_TYPE"
    with pytest.raises(DomainValidationError):
        dq.parse_marks_file(b"   ", "marks.csv")
    with pytest.raises(DomainValidationError) as exc:
        dq.parse_marks_file(b"not really an excel file", "marks.xlsx")
    assert exc.value.code == "UNREADABLE_FILE"


def test_parse_enforces_size_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dq.settings, "MAX_UPLOAD_MB", 0)
    with pytest.raises(DomainValidationError) as exc:
        dq.parse_marks_file(b"a,b\n1,2", "marks.csv")
    assert exc.value.code == "FILE_TOO_LARGE"


# --- mapping -------------------------------------------------------------------------------
def test_suggest_column_map_matches_names_codes_and_aliases() -> None:
    headers = ["Adm No", "Student Name", "Mathematics", "SCI", "English (100)", "Art"]
    cmap = dq.suggest_column_map(headers, SUBJECTS)
    assert cmap.admission_column == "Adm No"
    assert cmap.subjects == {
        "Student Name": None,
        "Mathematics": 1,
        "SCI": 2,
        "English (100)": 3,
        "Art": None,
    }


def test_suggest_column_map_prefix_fallback_and_roll_no() -> None:
    cmap = dq.suggest_column_map(["Roll No.", "Maths", "Sci", "Engl", "History"], SUBJECTS)
    assert cmap.admission_column == "Roll No."
    assert cmap.subjects == {"Maths": 1, "Sci": 2, "Engl": 3, "History": None}


def test_suggest_column_map_without_admission_column() -> None:
    cmap = dq.suggest_column_map(["Name", "Maths"], SUBJECTS)
    assert cmap.admission_column is None
    assert dq.ColumnMap.from_dict(cmap.to_dict()) == cmap


# --- validation ----------------------------------------------------------------------------
def test_clean_sheet_has_only_roster_warning() -> None:
    result = dq.validate_marks(
        sheet(["A001", "78", "40", "91"], ["a002", "45.5", "50", "0"], ["A003", "1", "2", "3"]),
        full_map(),
        ROSTER,
        CONFIGS,
    )
    # A004 is in section 1 but not in the file; B001 is in section 2 (not in file) -> ignored.
    assert codes(result) == [dq.STUDENT_NOT_IN_FILE]
    assert result.issues[0].severity == "warning"
    assert "A004" in result.issues[0].message
    assert result.can_commit
    row = result.rows[1]
    assert row.student_id == 12
    assert row.marks["maths"].value == Decimal("45.5")
    assert row.to_dict()["marks"]["maths"]["value"] == "45.5"


@pytest.mark.parametrize(
    ("cell", "code", "severity"),
    [
        ("101", dq.MARK_ABOVE_MAX, "error"),
        ("-1", dq.NEGATIVE_MARK, "error"),
        ("abc", dq.NON_NUMERIC, "error"),
        ("NaN", dq.NON_NUMERIC, "error"),
        ("", dq.MISSING_MARK, "warning"),
        ("AB", dq.ABSENT, "warning"),
        ("abs", dq.ABSENT, "warning"),
        ("A", dq.ABSENT, "warning"),
        ("Absent", dq.ABSENT, "warning"),
    ],
)
def test_cell_level_issue_codes(cell: str, code: str, severity: str) -> None:
    rows = [["A001", cell, "1", "1"], ["A002", "1", "1", "1"], ["A003", "1", "1", "1"]]
    rows.append(["A004", "1", "1", "1"])
    result = dq.validate_marks(sheet(*rows), full_map(), ROSTER, CONFIGS)
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert (issue.code, issue.severity, issue.row, issue.column) == (code, severity, 1, "maths")
    if code == dq.ABSENT:
        assert result.rows[0].marks["maths"].is_absent is True
        assert result.rows[0].marks["maths"].value is None


def test_mark_above_max_uses_subject_specific_limit() -> None:
    rows = [["A001", "1", "51", "1"], ["A002", "1", "50", "1"], ["A003", "1", "1", "1"]]
    rows.append(["A004", "1", "1", "1"])
    result = dq.validate_marks(sheet(*rows), full_map(), ROSTER, CONFIGS)
    assert [(i.code, i.row, i.column) for i in result.issues] == [(dq.MARK_ABOVE_MAX, 1, "sci")]
    assert not result.can_commit


def test_unknown_and_duplicate_students() -> None:
    rows = [
        ["A001", "1", "1", "1"],
        ["Z999", "1", "1", "1"],
        ["a001 ", "2", "2", "2"],
        ["", "1", "1", "1"],
    ]
    result = dq.validate_marks(sheet(*rows), full_map(), ROSTER, CONFIGS)
    by_code = {(i.code, i.row) for i in result.issues}
    assert (dq.UNKNOWN_STUDENT, 2) in by_code
    assert (dq.UNKNOWN_STUDENT, 4) in by_code
    assert (dq.DUPLICATE_STUDENT_ROW, 3) in by_code
    assert result.rows[1].student_id is None
    summary = result.summary()
    assert summary["errors"] == 3
    assert summary["by_code"][dq.UNKNOWN_STUDENT] == 2


def test_column_level_issues() -> None:
    headers = ["adm", "Student Name", "maths", "Art"]
    cmap = dq.ColumnMap(admission_column="adm", subjects={"Student Name": None, "maths": 1})
    rows = [["A001", "Asha", "1", "x"]]
    result = dq.validate_marks(
        sheet(*rows, headers=headers), cmap, ROSTER, CONFIGS, {2: "Science", 3: "English"}
    )
    found = [(i.code, i.column) for i in result.issues]
    assert (dq.UNMAPPED_COLUMN, "Art") in found
    assert (dq.UNMAPPED_COLUMN, "Student Name") not in found  # informational column
    missing = [i for i in result.issues if i.code == dq.MISSING_SUBJECT_COLUMN]
    assert len(missing) == 2
    assert 'subject "Science"' in missing[0].message
    assert all(i.severity == "warning" for i in result.issues)


def test_no_admission_column_is_error() -> None:
    result = dq.validate_marks(
        sheet(["A001", "1", "1", "1"]),
        dq.ColumnMap(admission_column=None, subjects={"maths": 1}),
        ROSTER,
        CONFIGS,
    )
    assert codes(result) == [dq.NO_ADMISSION_COLUMN]
    assert result.issues[0].severity == "error"
    assert result.rows == []
    assert not result.can_commit


def test_every_issue_code_has_a_severity_and_phrase() -> None:
    assert set(dq.ISSUE_SEVERITY) == set(dq._CODE_PHRASES)


def test_summarize_issues_text() -> None:
    clean = dq.ValidationResult(rows=[], issues=[])
    assert "No issues found" in dq.summarize_issues_text(clean)

    rows = [["A001", "AB", "1", "1"], ["A001", "200", "1", "1"]]
    result = dq.validate_marks(sheet(*rows), full_map(), ROSTER, CONFIGS)
    text = dq.summarize_issues_text(result)
    assert text.startswith("Checked 2 rows.")
    assert "1 duplicate student row" in text
    assert "1 mark is above the maximum" in text
    assert "must be fixed before committing" in text
    # Deterministic and identical when built from stored dicts.
    assert text == dq.describe_issues([i.to_dict() for i in result.issues], 2)
