"""FastAPI Router for Leave Management."""


from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from core.dependencies import get_current_user, require_roles
from core.models import LeaveStatus, Role, User
from database.session import get_db
from modules.leave.schemas import (
    LeaveApproveRequest,
    LeaveCreateRequest,
    LeaveRejectRequest,
    LeaveResponse,
    LeaveReviewRequest,
)
from modules.leave.service import (
    approve_leave_request,
    create_leave_request,
    get_leave_request,
    list_leave_requests,
    reject_leave_request,
    review_leave_request,
)

router = APIRouter(prefix="/leave", tags=["Leave Management"])


@router.post("", response_model=LeaveResponse, status_code=status.HTTP_201_CREATED)
def submit_leave(
    payload: LeaveCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeaveResponse:
    """Submit a leave request (Cadets, Leaders, Officers)."""
    return create_leave_request(db, current_user, payload)


@router.get("", response_model=list[LeaveResponse])
def list_leaves(
    status_filter: LeaveStatus | None = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LeaveResponse]:
    """List leave requests accessible within current user's scope."""
    return list_leave_requests(db, current_user, status_filter=status_filter)


@router.get("/{id}", response_model=LeaveResponse)
def get_leave(
    id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeaveResponse:
    """Retrieve details of a specific leave request."""
    return get_leave_request(db, current_user, id)


@router.post("/{id}/review", response_model=LeaveResponse)
def review_leave(
    id: int,
    payload: LeaveReviewRequest = LeaveReviewRequest(),
    current_user: User = Depends(require_roles(Role.CO, Role.ANO, Role.JUO, Role.LEADER)),
    db: Session = Depends(get_db),
) -> LeaveResponse:
    """Review a submitted leave request (Leader, JUO, ANO, CO)."""
    return review_leave_request(db, current_user, id, payload)


@router.post("/{id}/approve", response_model=LeaveResponse)
def approve_leave(
    id: int,
    payload: LeaveApproveRequest = LeaveApproveRequest(),
    current_user: User = Depends(require_roles(Role.CO, Role.ANO)),
    db: Session = Depends(get_db),
) -> LeaveResponse:
    """Final approval for a leave request with automatic presence synchronization (ANO, CO)."""
    return approve_leave_request(db, current_user, id, payload)


@router.post("/{id}/reject", response_model=LeaveResponse)
def reject_leave(
    id: int,
    payload: LeaveRejectRequest,
    current_user: User = Depends(require_roles(Role.CO, Role.ANO, Role.JUO, Role.LEADER)),
    db: Session = Depends(get_db),
) -> LeaveResponse:
    """Reject a leave request with mandatory rejection reason."""
    return reject_leave_request(db, current_user, id, payload)
