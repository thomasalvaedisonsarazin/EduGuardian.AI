"""Academic setup endpoints (Module 2): years, classes, subjects, teachers, students, exams.

Reads are open to any member of the active school; writes need school_admin/principal/coordinator.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import TenantContext, get_db, require_roles
from app.exceptions import DomainValidationError
from app.models import MembershipRole
from app.schemas.setup import (
    AcademicYearCreate,
    AcademicYearOut,
    AcademicYearUpdate,
    ClassSectionCreate,
    ClassSectionOut,
    ClassSectionUpdate,
    ExamCreate,
    ExamOut,
    ExamSubjectConfigIn,
    ExamSubjectConfigOut,
    ExamUpdate,
    StudentCreate,
    StudentImportResult,
    StudentList,
    StudentOut,
    StudentUpdate,
    SubjectCreate,
    SubjectOut,
    SubjectUpdate,
    TeacherCreate,
    TeacherOut,
    TeacherUpdate,
    TeachingAssignmentCreate,
    TeachingAssignmentOut,
    TeachingAssignmentUpdate,
)
from app.services import setup_service as svc
from app.services.setup_service import Actor

router = APIRouter(tags=["setup"])

DB = Annotated[Session, Depends(get_db)]
Member = Annotated[TenantContext, Depends(require_roles())]
Editor = Annotated[
    TenantContext,
    Depends(
        require_roles(
            MembershipRole.school_admin, MembershipRole.principal, MembershipRole.coordinator
        )
    ),
]


def _actor(ctx: TenantContext) -> Actor:
    return Actor(school_id=ctx.school_id, user_id=ctx.user.id)


def _no_content() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- academic years ---------------------------------------------------------------------------
@router.get("/academic-years", response_model=list[AcademicYearOut])
def list_academic_years(ctx: Member, db: DB) -> list[AcademicYearOut]:
    return [AcademicYearOut.model_validate(y) for y in svc.list_academic_years(db, ctx.school_id)]


@router.post("/academic-years", response_model=AcademicYearOut, status_code=201)
def create_academic_year(data: AcademicYearCreate, ctx: Editor, db: DB) -> AcademicYearOut:
    return AcademicYearOut.model_validate(svc.create_academic_year(db, _actor(ctx), data))


@router.get("/academic-years/{year_id}", response_model=AcademicYearOut)
def get_academic_year(year_id: int, ctx: Member, db: DB) -> AcademicYearOut:
    return AcademicYearOut.model_validate(svc.get_academic_year(db, ctx.school_id, year_id))


@router.patch("/academic-years/{year_id}", response_model=AcademicYearOut)
@router.put("/academic-years/{year_id}", response_model=AcademicYearOut, include_in_schema=False)
def update_academic_year(
    year_id: int, data: AcademicYearUpdate, ctx: Editor, db: DB
) -> AcademicYearOut:
    return AcademicYearOut.model_validate(svc.update_academic_year(db, _actor(ctx), year_id, data))


@router.delete("/academic-years/{year_id}", status_code=204)
def delete_academic_year(year_id: int, ctx: Editor, db: DB) -> Response:
    svc.delete_academic_year(db, _actor(ctx), year_id)
    return _no_content()


# --- classes ----------------------------------------------------------------------------------
@router.get("/classes", response_model=list[ClassSectionOut])
def list_classes(ctx: Member, db: DB, academic_year_id: int | None = None) -> list[ClassSectionOut]:
    return svc.list_class_sections(db, ctx.school_id, academic_year_id)


@router.post("/classes", response_model=ClassSectionOut, status_code=201)
def create_class(data: ClassSectionCreate, ctx: Editor, db: DB) -> ClassSectionOut:
    return svc.create_class_section(db, _actor(ctx), data)


@router.get("/classes/{class_id}", response_model=ClassSectionOut)
def get_class(class_id: int, ctx: Member, db: DB) -> ClassSectionOut:
    return svc.get_class_section_out(db, ctx.school_id, class_id)


@router.patch("/classes/{class_id}", response_model=ClassSectionOut)
@router.put("/classes/{class_id}", response_model=ClassSectionOut, include_in_schema=False)
def update_class(class_id: int, data: ClassSectionUpdate, ctx: Editor, db: DB) -> ClassSectionOut:
    return svc.update_class_section(db, _actor(ctx), class_id, data)


@router.delete("/classes/{class_id}", status_code=204)
def delete_class(class_id: int, ctx: Editor, db: DB) -> Response:
    svc.delete_class_section(db, _actor(ctx), class_id)
    return _no_content()


# --- subjects ---------------------------------------------------------------------------------
@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(ctx: Member, db: DB) -> list[SubjectOut]:
    return [SubjectOut.model_validate(s) for s in svc.list_subjects(db, ctx.school_id)]


@router.post("/subjects", response_model=SubjectOut, status_code=201)
def create_subject(data: SubjectCreate, ctx: Editor, db: DB) -> SubjectOut:
    return SubjectOut.model_validate(svc.create_subject(db, _actor(ctx), data))


@router.get("/subjects/{subject_id}", response_model=SubjectOut)
def get_subject(subject_id: int, ctx: Member, db: DB) -> SubjectOut:
    return SubjectOut.model_validate(svc.get_subject(db, ctx.school_id, subject_id))


@router.patch("/subjects/{subject_id}", response_model=SubjectOut)
@router.put("/subjects/{subject_id}", response_model=SubjectOut, include_in_schema=False)
def update_subject(subject_id: int, data: SubjectUpdate, ctx: Editor, db: DB) -> SubjectOut:
    return SubjectOut.model_validate(svc.update_subject(db, _actor(ctx), subject_id, data))


@router.delete("/subjects/{subject_id}", status_code=204)
def delete_subject(subject_id: int, ctx: Editor, db: DB) -> Response:
    svc.delete_subject(db, _actor(ctx), subject_id)
    return _no_content()


# --- teachers ---------------------------------------------------------------------------------
@router.get("/teachers", response_model=list[TeacherOut])
def list_teachers(ctx: Member, db: DB) -> list[TeacherOut]:
    return [TeacherOut.model_validate(t) for t in svc.list_teachers(db, ctx.school_id)]


@router.post("/teachers", response_model=TeacherOut, status_code=201)
def create_teacher(data: TeacherCreate, ctx: Editor, db: DB) -> TeacherOut:
    return TeacherOut.model_validate(svc.create_teacher(db, _actor(ctx), data))


@router.get("/teachers/{teacher_id}", response_model=TeacherOut)
def get_teacher(teacher_id: int, ctx: Member, db: DB) -> TeacherOut:
    return TeacherOut.model_validate(svc.get_teacher(db, ctx.school_id, teacher_id))


@router.patch("/teachers/{teacher_id}", response_model=TeacherOut)
@router.put("/teachers/{teacher_id}", response_model=TeacherOut, include_in_schema=False)
def update_teacher(teacher_id: int, data: TeacherUpdate, ctx: Editor, db: DB) -> TeacherOut:
    return TeacherOut.model_validate(svc.update_teacher(db, _actor(ctx), teacher_id, data))


@router.delete("/teachers/{teacher_id}", status_code=204)
def delete_teacher(teacher_id: int, ctx: Editor, db: DB) -> Response:
    svc.delete_teacher(db, _actor(ctx), teacher_id)
    return _no_content()


# --- teaching assignments ---------------------------------------------------------------------
@router.get("/teaching-assignments", response_model=list[TeachingAssignmentOut])
def list_teaching_assignments(
    ctx: Member,
    db: DB,
    teacher_id: int | None = None,
    class_section_id: int | None = None,
) -> list[TeachingAssignmentOut]:
    rows = svc.list_teaching_assignments(db, ctx.school_id, teacher_id, class_section_id)
    return [TeachingAssignmentOut.model_validate(r) for r in rows]


@router.post("/teaching-assignments", response_model=TeachingAssignmentOut, status_code=201)
def create_teaching_assignment(
    data: TeachingAssignmentCreate, ctx: Editor, db: DB
) -> TeachingAssignmentOut:
    return TeachingAssignmentOut.model_validate(
        svc.create_teaching_assignment(db, _actor(ctx), data)
    )


@router.get("/teaching-assignments/{ta_id}", response_model=TeachingAssignmentOut)
def get_teaching_assignment(ta_id: int, ctx: Member, db: DB) -> TeachingAssignmentOut:
    return TeachingAssignmentOut.model_validate(
        svc.get_teaching_assignment(db, ctx.school_id, ta_id)
    )


@router.patch("/teaching-assignments/{ta_id}", response_model=TeachingAssignmentOut)
@router.put(
    "/teaching-assignments/{ta_id}", response_model=TeachingAssignmentOut, include_in_schema=False
)
def update_teaching_assignment(
    ta_id: int, data: TeachingAssignmentUpdate, ctx: Editor, db: DB
) -> TeachingAssignmentOut:
    return TeachingAssignmentOut.model_validate(
        svc.update_teaching_assignment(db, _actor(ctx), ta_id, data)
    )


@router.delete("/teaching-assignments/{ta_id}", status_code=204)
def delete_teaching_assignment(ta_id: int, ctx: Editor, db: DB) -> Response:
    svc.delete_teaching_assignment(db, _actor(ctx), ta_id)
    return _no_content()


# --- students ---------------------------------------------------------------------------------
@router.get("/students", response_model=StudentList)
def list_students(
    ctx: Member,
    db: DB,
    class_section_id: int | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> StudentList:
    items, total = svc.list_students(db, ctx.school_id, class_section_id, q, limit, offset)
    return StudentList(items=[StudentOut.model_validate(s) for s in items], total=total)


@router.post("/students", response_model=StudentOut, status_code=201)
def create_student(data: StudentCreate, ctx: Editor, db: DB) -> StudentOut:
    return StudentOut.model_validate(svc.create_student(db, _actor(ctx), data))


@router.post("/students/import", response_model=StudentImportResult)
def import_students(
    ctx: Editor, db: DB, file: Annotated[UploadFile, File()]
) -> StudentImportResult:
    content = file.file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise DomainValidationError(f"File is larger than {settings.MAX_UPLOAD_MB} MB")
    return svc.import_students(db, _actor(ctx), content, file.filename or "upload.csv")


@router.get("/students/{student_id}", response_model=StudentOut)
def get_student(student_id: int, ctx: Member, db: DB) -> StudentOut:
    return StudentOut.model_validate(svc.get_student(db, ctx.school_id, student_id))


@router.patch("/students/{student_id}", response_model=StudentOut)
@router.put("/students/{student_id}", response_model=StudentOut, include_in_schema=False)
def update_student(student_id: int, data: StudentUpdate, ctx: Editor, db: DB) -> StudentOut:
    return StudentOut.model_validate(svc.update_student(db, _actor(ctx), student_id, data))


@router.delete("/students/{student_id}", status_code=204)
def delete_student(student_id: int, ctx: Editor, db: DB) -> Response:
    svc.delete_student(db, _actor(ctx), student_id)
    return _no_content()


# --- exams ------------------------------------------------------------------------------------
@router.get("/exams", response_model=list[ExamOut])
def list_exams(ctx: Member, db: DB, academic_year_id: int | None = None) -> list[ExamOut]:
    return [ExamOut.model_validate(e) for e in svc.list_exams(db, ctx.school_id, academic_year_id)]


@router.post("/exams", response_model=ExamOut, status_code=201)
def create_exam(data: ExamCreate, ctx: Editor, db: DB) -> ExamOut:
    return ExamOut.model_validate(svc.create_exam(db, _actor(ctx), data))


@router.get("/exams/{exam_id}", response_model=ExamOut)
def get_exam(exam_id: int, ctx: Member, db: DB) -> ExamOut:
    return ExamOut.model_validate(svc.get_exam(db, ctx.school_id, exam_id))


@router.patch("/exams/{exam_id}", response_model=ExamOut)
@router.put("/exams/{exam_id}", response_model=ExamOut, include_in_schema=False)
def update_exam(exam_id: int, data: ExamUpdate, ctx: Editor, db: DB) -> ExamOut:
    return ExamOut.model_validate(svc.update_exam(db, _actor(ctx), exam_id, data))


@router.delete("/exams/{exam_id}", status_code=204)
def delete_exam(exam_id: int, ctx: Editor, db: DB) -> Response:
    svc.delete_exam(db, _actor(ctx), exam_id)
    return _no_content()


@router.get("/exams/{exam_id}/subjects", response_model=list[ExamSubjectConfigOut])
def list_exam_subjects(exam_id: int, ctx: Member, db: DB) -> list[ExamSubjectConfigOut]:
    return svc.list_exam_subjects(db, ctx.school_id, exam_id)


@router.put("/exams/{exam_id}/subjects", response_model=list[ExamSubjectConfigOut])
@router.post(
    "/exams/{exam_id}/subjects",
    response_model=list[ExamSubjectConfigOut],
    include_in_schema=False,
)
def replace_exam_subjects(
    exam_id: int, configs: list[ExamSubjectConfigIn], ctx: Editor, db: DB
) -> list[ExamSubjectConfigOut]:
    return svc.replace_exam_subjects(db, _actor(ctx), exam_id, configs)
