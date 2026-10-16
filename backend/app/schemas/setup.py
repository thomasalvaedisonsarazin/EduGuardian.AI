"""Pydantic schemas for Module 2 (Academic Setup)."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _strip(value: str) -> str:
    return value.strip()


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- academic years ---------------------------------------------------------------------------
class AcademicYearCreate(BaseModel):
    label: str = Field(min_length=1, max_length=20, examples=["2026-27"])
    is_current: bool = False

    @field_validator("label")
    @classmethod
    def _strip_label(cls, v: str) -> str:
        return _strip(v)


class AcademicYearUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=20)
    is_current: bool | None = None


class AcademicYearOut(_ORM):
    id: int
    school_id: int
    label: str
    is_current: bool


# --- class sections ---------------------------------------------------------------------------
class ClassSectionCreate(BaseModel):
    academic_year_id: int
    grade: int = Field(ge=1, le=12)
    section: str = Field(min_length=1, max_length=10)

    @field_validator("section")
    @classmethod
    def _norm_section(cls, v: str) -> str:
        return v.strip().upper()


class ClassSectionUpdate(BaseModel):
    academic_year_id: int | None = None
    grade: int | None = Field(default=None, ge=1, le=12)
    section: str | None = Field(default=None, min_length=1, max_length=10)

    @field_validator("section")
    @classmethod
    def _norm_section(cls, v: str | None) -> str | None:
        return v.strip().upper() if v is not None else None


class ClassSectionOut(_ORM):
    id: int
    school_id: int
    academic_year_id: int
    grade: int
    section: str
    student_count: int = 0


# --- subjects ---------------------------------------------------------------------------------
class SubjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=20)

    @field_validator("name", "code")
    @classmethod
    def _strip_fields(cls, v: str) -> str:
        return v.strip()


class SubjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=20)


class SubjectOut(_ORM):
    id: int
    school_id: int
    name: str
    code: str


# --- teachers ---------------------------------------------------------------------------------
class TeacherCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    user_id: int | None = None


class TeacherUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    user_id: int | None = None


class TeacherOut(_ORM):
    id: int
    school_id: int
    user_id: int | None
    full_name: str


# --- teaching assignments ---------------------------------------------------------------------
class TeachingAssignmentCreate(BaseModel):
    teacher_id: int
    class_section_id: int
    subject_id: int
    is_class_teacher: bool = False


class TeachingAssignmentUpdate(BaseModel):
    teacher_id: int | None = None
    class_section_id: int | None = None
    subject_id: int | None = None
    is_class_teacher: bool | None = None


class TeachingAssignmentOut(_ORM):
    id: int
    school_id: int
    teacher_id: int
    class_section_id: int
    subject_id: int
    is_class_teacher: bool


# --- students ---------------------------------------------------------------------------------
class StudentCreate(BaseModel):
    class_section_id: int
    admission_no: str = Field(min_length=1, max_length=50)
    full_name: str = Field(min_length=1, max_length=200)

    @field_validator("admission_no", "full_name")
    @classmethod
    def _strip_fields(cls, v: str) -> str:
        return v.strip()


class StudentUpdate(BaseModel):
    class_section_id: int | None = None
    admission_no: str | None = Field(default=None, min_length=1, max_length=50)
    full_name: str | None = Field(default=None, min_length=1, max_length=200)


class StudentOut(_ORM):
    id: int
    school_id: int
    class_section_id: int
    admission_no: str
    full_name: str
    pseudo_id: str


class StudentList(BaseModel):
    items: list[StudentOut]
    total: int


class ImportRowError(BaseModel):
    row: int
    message: str


class StudentImportResult(BaseModel):
    created: int
    updated: int
    errors: list[ImportRowError]


# --- exams ------------------------------------------------------------------------------------
class ExamCreate(BaseModel):
    academic_year_id: int
    name: str = Field(min_length=1, max_length=100)
    sequence: int = Field(default=1, ge=1)
    held_on: date | None = None


class ExamUpdate(BaseModel):
    academic_year_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    sequence: int | None = Field(default=None, ge=1)
    held_on: date | None = None


class ExamOut(_ORM):
    id: int
    school_id: int
    academic_year_id: int
    name: str
    sequence: int
    held_on: date | None


class ExamSubjectConfigIn(BaseModel):
    subject_id: int
    max_marks: Decimal = Field(gt=0, le=1000)
    pass_marks: Decimal = Field(ge=0, le=1000)

    @model_validator(mode="after")
    def _pass_le_max(self) -> "ExamSubjectConfigIn":
        if self.pass_marks > self.max_marks:
            raise ValueError("pass_marks must be less than or equal to max_marks")
        return self


class ExamSubjectConfigOut(_ORM):
    id: int
    school_id: int
    exam_id: int
    subject_id: int
    subject_name: str
    subject_code: str
    max_marks: Decimal
    pass_marks: Decimal
