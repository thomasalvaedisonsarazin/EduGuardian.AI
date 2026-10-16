"""Marks import endpoints (Data Quality Agent). Thin layer over ``app.services.import_service``."""

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import TenantContext, get_db, require_roles
from app.exceptions import DomainValidationError
from app.schemas.imports import (
    ColumnMapUpdate,
    CommitResult,
    ImportBatchDetail,
    ImportBatchListItem,
)
from app.services import import_service

router = APIRouter(prefix="/imports", tags=["imports"])

_import_roles = require_roles("school_admin", "principal", "coordinator", "teacher")


@router.get("/template")
def download_template(
    exam_id: int = Query(...),
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(_import_roles),
) -> Response:
    """CSV template: admission_no + one column per exam subject, prefilled with students."""
    filename, content = import_service.build_template(db, ctx, exam_id)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("", response_model=ImportBatchDetail, status_code=201)
def upload_import(
    exam_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(_import_roles),
) -> ImportBatchDetail:
    """Upload a CSV/XLSX marks file for an exam; it is parsed, mapped and validated."""
    # Sync endpoint (runs in the threadpool) -> read the spooled file synchronously.
    content = file.file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise DomainValidationError(
            f"File is larger than the {settings.MAX_UPLOAD_MB} MB limit", code="FILE_TOO_LARGE"
        )
    return import_service.upload(db, ctx, exam_id, file.filename or "upload", content)


@router.get("", response_model=list[ImportBatchListItem])
def list_imports(
    exam_id: int | None = Query(None),
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(_import_roles),
) -> list[ImportBatchListItem]:
    return import_service.list_batches(db, ctx, exam_id)


@router.get("/{batch_id}", response_model=ImportBatchDetail)
def get_import(
    batch_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(_import_roles),
) -> ImportBatchDetail:
    return import_service.get_detail(db, ctx, batch_id)


@router.put("/{batch_id}/mapping", response_model=ImportBatchDetail)
def update_mapping(
    batch_id: int,
    payload: ColumnMapUpdate,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(_import_roles),
) -> ImportBatchDetail:
    return import_service.update_mapping(db, ctx, batch_id, payload)


@router.post("/{batch_id}/commit", response_model=CommitResult)
def commit_import(
    batch_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(_import_roles),
) -> CommitResult:
    return import_service.commit(db, ctx, batch_id)


@router.post("/{batch_id}/reject", response_model=ImportBatchDetail)
def reject_import(
    batch_id: int,
    db: Session = Depends(get_db),
    ctx: TenantContext = Depends(_import_roles),
) -> ImportBatchDetail:
    return import_service.reject(db, ctx, batch_id)
