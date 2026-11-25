"""FastAPI Router for Attendance and Parade Operations."""


from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_current_user, require_roles
from core.models import AttendanceStatus, Role, User
from modules.attendance.schemas import (
    ApproveAttendanceRequest,
    AttendanceRecordResponse,
    CorrectRecordRequest,
    ParadeCreateRequest,
    ParadeDetailResponse,
    ParadeResponse,
    ReviewAttendanceRequest,
    SubmitAttendanceRequest,
)
from modules.attendance.service import (
    approve_attendance,
    correct_attendance_record,
    create_parade,
    get_parade_detail,
    get_parades,
    lock_attendance,
    review_attendance,
    submit_squad_attendance,
)

router = APIRouter(prefix="/attendance", tags=["Attendance Management"])


@router.post("/parades", response_model=ParadeResponse, status_code=status.HTTP_201_CREATED)
def create_parade_session(
    payload: ParadeCreateRequest,
    current_user: User = Depends(require_roles(Role.CO, Role.ANO, Role.JUO)),
    db: Session = Depends(get_db),
) -> ParadeResponse:
    """Create a new parade or attendance session (CO, ANO, JUO)."""
    return create_parade(db, current_user, payload)


@router.get("/parades", response_model=list[ParadeResponse])
def list_parades(
    status_filter: AttendanceStatus | None = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ParadeResponse]:
    """List parade sessions accessible within the current user's scope."""
    return get_parades(db, current_user, status_filter=status_filter)


@router.get("/parades/{id}", response_model=ParadeDetailResponse)
def get_parade(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ParadeDetailResponse:
    """Retrieve full parade details and cadet attendance records within user scope."""
    return get_parade_detail(db, current_user, id)


@router.post("/{id}/submit", response_model=ParadeDetailResponse)
def submit_attendance(
    id: int,
    payload: SubmitAttendanceRequest,
    current_user: User = Depends(require_roles(Role.CO, Role.ANO, Role.JUO, Role.LEADER)),
    db: Session = Depends(get_db),
) -> ParadeDetailResponse:
    """Submit squad-level attendance entries (Leader, JUO, ANO, CO)."""
    return submit_squad_attendance(db, current_user, id, payload)


@router.post("/{id}/review", response_model=ParadeResponse)
def juo_review_attendance(
    id: int,
    payload: ReviewAttendanceRequest = ReviewAttendanceRequest(),
    current_user: User = Depends(require_roles(Role.CO, Role.ANO, Role.JUO)),
    db: Session = Depends(get_db),
) -> ParadeResponse:
    """Review submitted attendance (JUO review step)."""
    return review_attendance(db, current_user, id, payload)


@router.post("/{id}/approve", response_model=ParadeResponse)
def ano_approve_attendance(
    id: int,
    payload: ApproveAttendanceRequest = ApproveAttendanceRequest(),
    current_user: User = Depends(require_roles(Role.CO, Role.ANO)),
    db: Session = Depends(get_db),
) -> ParadeResponse:
    """Formally approve attendance session (ANO approval step)."""
    return approve_attendance(db, current_user, id, payload)


@router.post("/{id}/lock", response_model=ParadeResponse)
def lock_parade_attendance(
    id: int,
    current_user: User = Depends(require_roles(Role.CO, Role.ANO)),
    db: Session = Depends(get_db),
) -> ParadeResponse:
    """Lock parade attendance records against standard modifications (ANO, CO)."""
    return lock_attendance(db, current_user, id)


@router.patch("/{id}/records/{record_id}", response_model=AttendanceRecordResponse)
def correct_record(
    id: int,
    record_id: int,
    payload: CorrectRecordRequest,
    current_user: User = Depends(require_roles(Role.CO, Role.ANO)),
    db: Session = Depends(get_db),
) -> AttendanceRecordResponse:
    """Authorized correction of an attendance record with mandatory audit reason (ANO, CO)."""
    return correct_attendance_record(db, current_user, id, record_id, payload)
