"""Reports endpoints (Module 6, Reporting Agent).

POST   /reports                 generate a PDF/XLSX report (any member; teachers: own scope)
GET    /reports                 list (?exam_id=&kind=&run_id=), newest first
GET    /reports/{id}/download   file download
DELETE /reports/{id}            delete file + row (school_admin)
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.dependencies import TenantContext, get_db, require_roles
from app.models import MembershipRole, ReportKind
from app.schemas.reports import ReportCreate, ReportOut
from app.services import report_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])

DB = Annotated[Session, Depends(get_db)]
Member = Annotated[TenantContext, Depends(require_roles())]
Admin = Annotated[TenantContext, Depends(require_roles(MembershipRole.school_admin))]


@router.post("", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def create_report(data: ReportCreate, ctx: Member, db: DB) -> ReportOut:
    """Generate a report synchronously and return its metadata."""
    return report_service.create_report(db, ctx, data)


@router.get("", response_model=list[ReportOut])
def list_reports(
    ctx: Member,
    db: DB,
    exam_id: int | None = Query(default=None, gt=0),
    kind: ReportKind | None = None,
    run_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[ReportOut]:
    return report_service.list_reports(
        db, ctx, exam_id=exam_id, kind=kind, run_id=run_id, limit=limit
    )


@router.get("/{report_id}/download", response_class=FileResponse)
def download_report(report_id: int, ctx: Member, db: DB) -> FileResponse:
    file = report_service.get_report_file(db, ctx, report_id)
    return FileResponse(file.path, media_type=file.media_type, filename=file.filename)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(report_id: int, ctx: Admin, db: DB) -> Response:
    report_service.delete_report(db, ctx, report_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
