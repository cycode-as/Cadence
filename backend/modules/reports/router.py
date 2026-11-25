"""FastAPI Router for Reports and CSV Exports."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from core.dependencies import get_current_user
from core.models import User
from database.session import get_db
from modules.reports.schemas import (
    AttendanceSummaryResponse,
    LeaveSummaryResponse,
    ParticipationReportResponse,
)
from modules.reports.service import (
    export_attendance_csv,
    get_attendance_summary,
    get_leave_summary,
    get_participation_report,
)

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])


@router.get("/attendance", response_model=AttendanceSummaryResponse)
def get_attendance_report(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AttendanceSummaryResponse:
    """Retrieve unit/squad attendance summary metrics."""
    return get_attendance_summary(db, current_user)


@router.get("/leave", response_model=LeaveSummaryResponse)
def get_leave_report(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeaveSummaryResponse:
    """Retrieve leave statistics."""
    return get_leave_summary(db, current_user)


@router.get("/participation", response_model=ParticipationReportResponse)
def get_participation_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ParticipationReportResponse:
    """Retrieve per-cadet participation report."""
    return get_participation_report(db, current_user)


@router.get("/attendance/export")
def download_attendance_csv(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Download attendance dataset formatted as CSV."""
    csv_content = export_attendance_csv(db, current_user)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=cadence_attendance_report.csv"
        },
    )
