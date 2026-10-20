"""Data Quality Agent - deterministic checks for uploaded marks files.

Pure functions only (no DB, no I/O beyond decoding the given bytes) so the orchestrator can
reuse them later:

- :func:`parse_marks_file` turns CSV/XLSX bytes into a :class:`ParsedSheet` (all cells strings).
- :func:`suggest_column_map` guesses the admission-number column and header -> subject mapping.
- :func:`validate_marks` normalizes rows and produces a list of :class:`Issue` objects.
- :func:`summarize_issues_text` renders a deterministic English summary of the result.
"""

from __future__ import annotations

import io
import logging
import os
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import pandas as pd

from app.config import settings
from app.exceptions import DomainValidationError

logger = logging.getLogger(__name__)

AGENT_NAME = "DataQualityAgent"

Severity = Literal["error", "warning"]

ALLOWED_EXTENSIONS = (".csv", ".xlsx", ".xlsm")

# Issue codes ------------------------------------------------------------------------------
UNKNOWN_STUDENT = "UNKNOWN_STUDENT"
DUPLICATE_STUDENT_ROW = "DUPLICATE_STUDENT_ROW"
MARK_ABOVE_MAX = "MARK_ABOVE_MAX"
NEGATIVE_MARK = "NEGATIVE_MARK"
NON_NUMERIC = "NON_NUMERIC"
MISSING_MARK = "MISSING_MARK"
ABSENT = "ABSENT"
UNMAPPED_COLUMN = "UNMAPPED_COLUMN"
MISSING_SUBJECT_COLUMN = "MISSING_SUBJECT_COLUMN"
STUDENT_NOT_IN_FILE = "STUDENT_NOT_IN_FILE"
NO_ADMISSION_COLUMN = "NO_ADMISSION_COLUMN"

ISSUE_SEVERITY: dict[str, Severity] = {
    UNKNOWN_STUDENT: "error",
    DUPLICATE_STUDENT_ROW: "error",
    MARK_ABOVE_MAX: "error",
    NEGATIVE_MARK: "error",
    NON_NUMERIC: "error",
    NO_ADMISSION_COLUMN: "error",
    MISSING_MARK: "warning",
    ABSENT: "warning",
    UNMAPPED_COLUMN: "warning",
    MISSING_SUBJECT_COLUMN: "warning",
    STUDENT_NOT_IN_FILE: "warning",
}

ABSENT_TOKENS = frozenset({"ab", "abs", "a", "absent"})

# Normalized header aliases (see :func:`normalize_header`), in priority order.
ADMISSION_ALIASES: tuple[str, ...] = (
    "admissionno",
    "admissionnumber",
    "admissionnum",
    "admno",
    "admnno",
    "admnumber",
    "admnnumber",
    "admission",
    "admissionid",
    "enrollmentno",
    "enrolmentno",
    "regno",
    "registrationno",
    "rollno",
    "rollnumber",
    "roll",
)

# Informational columns that are expected in a marks sheet and silently ignored.
INFO_COLUMNS = frozenset(
    {
        "name",
        "studentname",
        "fullname",
        "class",
        "section",
        "grade",
        "classsection",
        "sno",
        "srno",
        "slno",
        "serial",
        "serialno",
        "remarks",
        "total",
        "percentage",
        "result",
        "rank",
    }
)


# --- data structures ----------------------------------------------------------------------
@dataclass(frozen=True)
class ParsedSheet:
    """A parsed sheet: stripped headers plus data rows (all cells as stripped strings)."""

    headers: list[str]
    rows: list[list[str]]


@dataclass(frozen=True)
class SubjectRef:
    id: int
    name: str
    code: str


@dataclass(frozen=True)
class StudentRef:
    id: int
    admission_no: str
    class_section_id: int


@dataclass(frozen=True)
class SubjectLimits:
    max_marks: Decimal
    pass_marks: Decimal


@dataclass
class ColumnMap:
    """Which header holds the admission number and which header maps to which subject."""

    admission_column: str | None
    subjects: dict[str, int | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"admission_column": self.admission_column, "subjects": dict(self.subjects)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> ColumnMap:
        data = data or {}
        raw_subjects = data.get("subjects") or {}
        subjects = {
            str(h): (int(sid) if sid is not None else None) for h, sid in raw_subjects.items()
        }
        admission = data.get("admission_column")
        return cls(admission_column=str(admission) if admission else None, subjects=subjects)


@dataclass(frozen=True)
class Issue:
    code: str
    severity: Severity
    message: str
    row: int | None = None  # 1-based data row (header excluded)
    column: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "row": self.row,
            "column": self.column,
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass(frozen=True)
class MarkCell:
    subject_id: int
    raw: str
    value: Decimal | None
    is_absent: bool


@dataclass
class NormalizedRow:
    row: int
    admission_no: str
    student_id: int | None
    marks: dict[str, MarkCell] = field(default_factory=dict)  # header -> cell

    def to_dict(self) -> dict[str, Any]:
        """JSON-safe representation (decimals as strings)."""
        return {
            "row": self.row,
            "admission_no": self.admission_no,
            "student_id": self.student_id,
            "marks": {
                header: {
                    "subject_id": cell.subject_id,
                    "raw": cell.raw,
                    "value": str(cell.value) if cell.value is not None else None,
                    "is_absent": cell.is_absent,
                }
                for header, cell in self.marks.items()
            },
        }


@dataclass
class ValidationResult:
    rows: list[NormalizedRow]
    issues: list[Issue]

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def can_commit(self) -> bool:
        return self.error_count == 0 and bool(self.rows)

    def summary(self) -> dict[str, Any]:
        return summarize_issues(self.issues)


def make_issue(
    code: str, message: str, *, row: int | None = None, column: str | None = None
) -> Issue:
    return Issue(code=code, severity=ISSUE_SEVERITY[code], message=message, row=row, column=column)


def summarize_issues(issues: Iterable[Issue | Mapping[str, Any]]) -> dict[str, Any]:
    """Counts by severity and by code. Accepts Issue objects or their dict form."""
    by_code: Counter[str] = Counter()
    by_severity: Counter[str] = Counter()
    for issue in issues:
        code = issue.code if isinstance(issue, Issue) else str(issue.get("code"))
        severity = issue.severity if isinstance(issue, Issue) else str(issue.get("severity"))
        by_code[code] += 1
        by_severity[severity] += 1
    return {
        "errors": by_severity.get("error", 0),
        "warnings": by_severity.get("warning", 0),
        "by_code": dict(sorted(by_code.items())),
    }


# --- helpers -------------------------------------------------------------------------------
def normalize_header(value: str) -> str:
    """Lowercase, drop a trailing "(...)" hint and every non-alphanumeric character."""
    text = re.sub(r"\(.*?\)|\[.*?\]", "", value.lower())
    return re.sub(r"[^a-z0-9]", "", text)


def normalize_admission_no(value: str) -> str:
    """Canonical form used to match admission numbers ("A-001 " == "a-001"; "123.0" == "123")."""
    text = value.strip()
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", 1)[0]
    return text.upper()


def _clean_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:  # NaN
        return ""
    return str(value).strip()


# --- parsing -------------------------------------------------------------------------------
def parse_marks_file(content: bytes, filename: str) -> ParsedSheet:
    """Parse CSV or XLSX bytes into a :class:`ParsedSheet`. Every cell is read as a string.

    Raises :class:`DomainValidationError` for unsupported extensions, oversize/empty files
    and unreadable content.
    """
    name = (filename or "").lower().strip()
    if not name.endswith(ALLOWED_EXTENSIONS):
        raise DomainValidationError(
            "Unsupported file type - upload a .csv or .xlsx file", code="UNSUPPORTED_FILE_TYPE"
        )
    if len(content) > settings.max_upload_bytes:
        raise DomainValidationError(
            f"File is larger than the {settings.MAX_UPLOAD_MB} MB limit", code="FILE_TOO_LARGE"
        )
    if not content.strip():
        raise DomainValidationError("The uploaded file is empty", code="EMPTY_FILE")

    try:
        if name.endswith(".csv"):
            frame = _read_csv(content)
        else:
            frame = pd.read_excel(
                io.BytesIO(content),
                sheet_name=0,
                dtype=str,
                keep_default_na=False,
                engine="openpyxl",
                nrows=settings.MAX_IMPORT_ROWS + 1,
            )
    except DomainValidationError:
        raise
    except Exception as exc:  # pandas/openpyxl raise many different error types
        logger.info("Could not parse uploaded file %s: %s", filename, exc)
        raise DomainValidationError(
            "Could not read the file - check that it is a valid CSV or Excel sheet",
            code="UNREADABLE_FILE",
        ) from exc

    if len(frame) > settings.MAX_IMPORT_ROWS:
        raise DomainValidationError(
            f"The file has more than {settings.MAX_IMPORT_ROWS} rows - split it into smaller files",
            code="TOO_MANY_ROWS",
        )

    headers = [_clean_cell(h) for h in frame.columns]
    rows = [[_clean_cell(v) for v in record] for record in frame.itertuples(index=False)]

    # Drop unnamed columns that are entirely blank (trailing commas, stray Excel formatting).
    keep = [
        idx
        for idx, header in enumerate(headers)
        if not (header.startswith("Unnamed:") or header == "") or any(r[idx] for r in rows)
    ]
    headers = [headers[i] for i in keep]
    rows = [[r[i] for i in keep] for r in rows]
    # Drop fully blank rows.
    rows = [r for r in rows if any(cell for cell in r)]

    if not headers:
        raise DomainValidationError("The file has no header row", code="EMPTY_FILE")
    return ParsedSheet(headers=headers, rows=rows)


def _read_csv(content: bytes) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return pd.read_csv(
                io.BytesIO(content),
                dtype=str,
                keep_default_na=False,
                encoding=encoding,
                skipinitialspace=True,
                nrows=settings.MAX_IMPORT_ROWS + 1,
            )
        except UnicodeDecodeError:
            continue
    raise DomainValidationError("Could not decode the CSV file", code="UNREADABLE_FILE")


# --- column mapping ------------------------------------------------------------------------
def find_admission_column(headers: Iterable[str]) -> str | None:
    normalized = {h: normalize_header(h) for h in headers}
    for alias in ADMISSION_ALIASES:
        for header, norm in normalized.items():
            if norm == alias:
                return header
    return None


def suggest_column_map(headers: list[str], subjects: list[SubjectRef]) -> ColumnMap:
    """Guess the admission column and map the remaining headers to subjects.

    Matching is case/punctuation-insensitive on subject name or code; a prefix match
    ("Math" -> "Mathematics") is used as a fallback. Each subject is mapped at most once.
    """
    admission = find_admission_column(headers)
    used: set[int] = set()
    mapping: dict[str, int | None] = {}

    def exact(norm: str) -> SubjectRef | None:
        for s in subjects:
            if s.id not in used and norm in (normalize_header(s.name), normalize_header(s.code)):
                return s
        return None

    def prefix(norm: str) -> SubjectRef | None:
        """Best fuzzy match: one is a prefix of the other, or they share a long prefix."""
        if len(norm) < 3:
            return None
        best: tuple[int, SubjectRef] | None = None
        for s in subjects:
            name = normalize_header(s.name)
            if s.id in used or len(name) < 3:
                continue
            shared = len(os.path.commonprefix([norm, name]))
            shortest = min(len(norm), len(name))
            close = shared == shortest or (shared >= 4 and shared >= 0.6 * shortest)
            if close and (best is None or shared > best[0]):
                best = (shared, s)
        return best[1] if best else None

    pending: list[str] = []
    for header in headers:
        if header == admission:
            continue
        match = exact(normalize_header(header))
        if match:
            used.add(match.id)
            mapping[header] = match.id
        else:
            mapping[header] = None
            pending.append(header)
    for header in pending:
        match = prefix(normalize_header(header))
        if match:
            used.add(match.id)
            mapping[header] = match.id
    return ColumnMap(admission_column=admission, subjects=mapping)


# --- validation ----------------------------------------------------------------------------
def _parse_mark(raw: str) -> Decimal | None:
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def validate_marks(
    sheet: ParsedSheet,
    column_map: ColumnMap,
    roster: Mapping[str, StudentRef],
    configs: Mapping[int, SubjectLimits | tuple[Decimal, Decimal]],
    subject_names: Mapping[int, str] | None = None,
) -> ValidationResult:
    """Run every deterministic data-quality check.

    ``roster`` maps admission_no -> StudentRef for every student eligible for the exam.
    ``configs`` maps subject_id -> limits (``SubjectLimits`` or ``(max, pass)``) for the exam.
    ``subject_names`` (optional) is only used to make messages friendlier.
    """
    names = subject_names or {}
    issues: list[Issue] = []
    rows: list[NormalizedRow] = []
    limits = {
        sid: (c if isinstance(c, SubjectLimits) else SubjectLimits(Decimal(c[0]), Decimal(c[1])))
        for sid, c in configs.items()
    }
    roster_by_key = {normalize_admission_no(k): v for k, v in roster.items()}

    adm_col = column_map.admission_column
    if not adm_col or adm_col not in sheet.headers:
        issues.append(
            make_issue(
                NO_ADMISSION_COLUMN,
                "No admission-number column found - map one column to the admission number",
            )
        )
        return ValidationResult(rows=rows, issues=issues)

    adm_idx = sheet.headers.index(adm_col)
    subject_cols: list[tuple[int, str, int]] = []  # (index, header, subject_id)
    mapped_subjects: set[int] = set()
    for idx, header in enumerate(sheet.headers):
        if idx == adm_idx:
            continue
        sid = column_map.subjects.get(header)
        if sid is not None:
            subject_cols.append((idx, header, sid))
            mapped_subjects.add(sid)
        elif normalize_header(header) not in INFO_COLUMNS:
            issues.append(
                make_issue(
                    UNMAPPED_COLUMN,
                    f'Column "{header}" is not mapped to a subject and will be ignored',
                    column=header,
                )
            )

    for sid in sorted(set(limits) - mapped_subjects):
        issues.append(
            make_issue(
                MISSING_SUBJECT_COLUMN,
                f'No column is mapped to subject "{names.get(sid, f"#{sid}")}"; '
                "its marks will not be imported",
                column=None,
            )
        )

    seen: dict[str, int] = {}
    matched_students: set[int] = set()
    for row_no, cells in enumerate(sheet.rows, start=1):
        raw_adm = cells[adm_idx] if adm_idx < len(cells) else ""
        key = normalize_admission_no(raw_adm)
        student = roster_by_key.get(key) if key else None
        if not key:
            issues.append(
                make_issue(UNKNOWN_STUDENT, "Admission number is blank", row=row_no, column=adm_col)
            )
        elif student is None:
            issues.append(
                make_issue(
                    UNKNOWN_STUDENT,
                    f'Admission number "{raw_adm}" does not match any student',
                    row=row_no,
                    column=adm_col,
                )
            )
        if key and key in seen:
            issues.append(
                make_issue(
                    DUPLICATE_STUDENT_ROW,
                    f'Admission number "{raw_adm}" also appears on row {seen[key]}',
                    row=row_no,
                    column=adm_col,
                )
            )
        elif key:
            seen[key] = row_no
        if student is not None:
            matched_students.add(student.id)

        normalized = NormalizedRow(
            row=row_no, admission_no=raw_adm, student_id=student.id if student else None
        )
        for idx, header, sid in subject_cols:
            raw = cells[idx] if idx < len(cells) else ""
            normalized.marks[header] = _check_cell(
                raw, row_no, header, sid, limits.get(sid), issues
            )
        rows.append(normalized)

    # Roster students missing from the file, limited to the class sections present in it.
    sections = {s.class_section_id for s in roster_by_key.values() if s.id in matched_students}
    for _key, student in sorted(roster_by_key.items()):
        if student.class_section_id in sections and student.id not in matched_students:
            issues.append(
                make_issue(
                    STUDENT_NOT_IN_FILE,
                    f'Student "{student.admission_no}" is on the class roster but not in the file',
                    column=adm_col,
                )
            )
    return ValidationResult(rows=rows, issues=issues)


def _check_cell(
    raw: str,
    row_no: int,
    header: str,
    subject_id: int,
    limit: SubjectLimits | None,
    issues: list[Issue],
) -> MarkCell:
    if raw == "":
        issues.append(make_issue(MISSING_MARK, "Mark is blank", row=row_no, column=header))
        return MarkCell(subject_id=subject_id, raw=raw, value=None, is_absent=False)
    if raw.lower().rstrip(".") in ABSENT_TOKENS:
        issues.append(make_issue(ABSENT, "Marked absent", row=row_no, column=header))
        return MarkCell(subject_id=subject_id, raw=raw, value=None, is_absent=True)
    value = _parse_mark(raw)
    if value is None:
        issues.append(
            make_issue(NON_NUMERIC, f'"{raw}" is not a number', row=row_no, column=header)
        )
        return MarkCell(subject_id=subject_id, raw=raw, value=None, is_absent=False)
    if value < 0:
        issues.append(
            make_issue(NEGATIVE_MARK, f"Mark {raw} is negative", row=row_no, column=header)
        )
    elif limit is not None and value > limit.max_marks:
        issues.append(
            make_issue(
                MARK_ABOVE_MAX,
                f"Mark {raw} is above the maximum of {limit.max_marks.normalize():f}",
                row=row_no,
                column=header,
            )
        )
    return MarkCell(subject_id=subject_id, raw=raw, value=value, is_absent=False)


# --- summary -------------------------------------------------------------------------------
_CODE_PHRASES: dict[str, tuple[str, str]] = {
    UNKNOWN_STUDENT: ("row has an unknown admission number", "rows have unknown admission numbers"),
    DUPLICATE_STUDENT_ROW: ("duplicate student row", "duplicate student rows"),
    MARK_ABOVE_MAX: ("mark is above the maximum", "marks are above the maximum"),
    NEGATIVE_MARK: ("mark is negative", "marks are negative"),
    NON_NUMERIC: ("mark is not a number", "marks are not numbers"),
    NO_ADMISSION_COLUMN: ("admission-number column is missing", "admission columns are missing"),
    MISSING_MARK: ("mark is blank", "marks are blank"),
    ABSENT: ("mark is recorded as absent", "marks are recorded as absent"),
    UNMAPPED_COLUMN: ("column is not mapped", "columns are not mapped"),
    MISSING_SUBJECT_COLUMN: (
        "configured subject has no column",
        "configured subjects have no column",
    ),
    STUDENT_NOT_IN_FILE: ("roster student is missing", "roster students are missing"),
}


def summarize_issues_text(result: ValidationResult) -> str:
    """Deterministic plain-English summary of a validation result."""
    return describe_issues(result.issues, len(result.rows))


def describe_issues(issues: Iterable[Issue | Mapping[str, Any]], row_count: int) -> str:
    """Plain-English summary from issues (objects or stored dicts) and the number of rows."""
    pairs = [
        (i.code, i.severity)
        if isinstance(i, Issue)
        else (str(i.get("code")), str(i.get("severity")))
        for i in issues
    ]
    head = f"Checked {row_count} row{'s' if row_count != 1 else ''}."
    if not pairs:
        return f"{head} No issues found - the file is ready to import."

    parts: list[str] = []
    for severity in ("error", "warning"):
        counts = Counter(code for code, sev in pairs if sev == severity)
        for code, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            singular, plural = _CODE_PHRASES.get(code, (code.lower(), code.lower()))
            parts.append(f"{n} {singular if n == 1 else plural}")
    errors = sum(1 for _, sev in pairs if sev == "error")
    warnings = sum(1 for _, sev in pairs if sev == "warning")
    verdict = (
        f"{errors} error{'s' if errors != 1 else ''} must be fixed before committing."
        if errors
        else "No blocking errors - the marks can be committed."
    )
    detail = "; ".join(parts)
    return f"{head} Found {errors} error(s) and {warnings} warning(s): {detail}. {verdict}"
