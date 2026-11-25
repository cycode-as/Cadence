"""Leave management service implementing state transitions and attendance synchronization."""


from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.models import (
    AttendanceRecord,
    AuditLog,
    LeaveRequest,
    LeaveStatus,
    ParadeSession,
    PresenceStatus,
    Role,
    User,
)
from modules.leave.schemas import (
    LeaveApproveRequest,
    LeaveCreateRequest,
    LeaveRejectRequest,
    LeaveResponse,
    LeaveReviewRequest,
)
from policy.permissions import check_scope


def map_leave_response(leave: LeaveRequest) -> LeaveResponse:
    """Format LeaveRequest entity into LeaveResponse schema."""
    return LeaveResponse(
        id=leave.id,
        cadet_id=leave.cadet_id,
        cadet_name=leave.cadet.full_name if leave.cadet else None,
        cadet_number=leave.cadet.cadet_number if leave.cadet else None,
        squad_id=leave.cadet.squad_id if leave.cadet else None,
        start_date=leave.start_date,
        end_date=leave.end_date,
        reason=leave.reason,
        status=leave.status,
        reviewed_by_id=leave.reviewed_by_id,
        approved_by_id=leave.approved_by_id,
        rejection_reason=leave.rejection_reason,
        created_at=leave.created_at,
        updated_at=leave.updated_at,
    )


def create_leave_request(
    db: Session,
    user: User,
    data: LeaveCreateRequest,
) -> LeaveResponse:
    """Submit a new leave request (Cadet or authorized personnel)."""
    leave = LeaveRequest(
        cadet_id=user.id,
        start_date=data.start_date,
        end_date=data.end_date,
        reason=data.reason,
        status=LeaveStatus.PENDING,
    )
    db.add(leave)
    db.flush()

    # Audit log entry
    audit = AuditLog(
        actor_id=user.id,
        action="LEAVE_SUBMITTED",
        resource_type="LeaveRequest",
        resource_id=str(leave.id),
        new_state=LeaveStatus.PENDING.value,
        reason=f"Leave requested from {data.start_date.date()} to {data.end_date.date()}",
    )
    db.add(audit)
    db.flush()

    return map_leave_response(leave)


def list_leave_requests(
    db: Session,
    user: User,
    status_filter: LeaveStatus | None = None,
) -> list[LeaveResponse]:
    """List leave requests based on user scope and permissions."""
    query = db.query(LeaveRequest).join(User, LeaveRequest.cadet_id == User.id)

    # Scope filtering
    if user.role == Role.CADET:
        query = query.filter(LeaveRequest.cadet_id == user.id)
    elif user.role == Role.LEADER:
        query = query.filter(User.squad_id == user.squad_id)
    elif user.role == Role.JUO:
        if user.squad_id:
            query = query.filter(User.squad_id == user.squad_id)
        else:
            query = query.filter(User.unit_id == user.unit_id)
    elif user.role in (Role.CO, Role.ANO):
        if user.unit_id:
            query = query.filter(User.unit_id == user.unit_id)

    if status_filter:
        query = query.filter(LeaveRequest.status == status_filter)

    leaves = query.order_by(LeaveRequest.created_at.desc()).all()
    return [map_leave_response(leave_item) for leave_item in leaves]


def get_leave_request(
    db: Session,
    user: User,
    leave_id: int,
) -> LeaveResponse:
    """Retrieve details of a specific leave request with scope enforcement."""
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found",
        )

    cadet = leave.cadet
    if not check_scope(
        user,
        target_unit_id=cadet.unit_id if cadet else None,
        target_squad_id=cadet.squad_id if cadet else None,
        target_cadet_id=leave.cadet_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access this leave request",
        )

    return map_leave_response(leave)


def review_leave_request(
    db: Session,
    user: User,
    leave_id: int,
    data: LeaveReviewRequest,
) -> LeaveResponse:
    """Leader or JUO reviews a submitted leave request: PENDING -> REVIEWED."""
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found",
        )

    if leave.status != LeaveStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot review leave request in status {leave.status.value}",
        )

    # Leader scope check
    cadet = leave.cadet
    if user.role == Role.LEADER and (not cadet or cadet.squad_id != user.squad_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Leaders may only review leave requests for cadets in their squad",
        )

    prev_state = leave.status.value
    leave.status = LeaveStatus.REVIEWED
    leave.reviewed_by_id = user.id
    db.add(leave)

    audit = AuditLog(
        actor_id=user.id,
        action="LEAVE_REVIEWED",
        resource_type="LeaveRequest",
        resource_id=str(leave.id),
        previous_state=prev_state,
        new_state=LeaveStatus.REVIEWED.value,
        reason=data.notes or "Leave reviewed by squad leadership",
    )
    db.add(audit)
    db.flush()

    return map_leave_response(leave)


def approve_leave_request(
    db: Session,
    user: User,
    leave_id: int,
    data: LeaveApproveRequest,
) -> LeaveResponse:
    """Final leave approval by ANO or CO with attendance presence synchronization.

    When approved:
    - Automatically updates or creates attendance records marking ON_LEAVE for all parades
      occurring within [start_date, end_date].
    """
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found",
        )

    if leave.status in (LeaveStatus.APPROVED, LeaveStatus.REJECTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve leave request already in status {leave.status.value}",
        )

    prev_state = leave.status.value
    leave.status = LeaveStatus.APPROVED
    leave.approved_by_id = user.id
    db.add(leave)

    # =========================================================================
    # Attendance Synchronization:
    # Synchronize presence records for any parades overlapping the approved leave
    # =========================================================================
    cadet = leave.cadet
    if cadet and cadet.unit_id:
        overlapping_parades = (
            db.query(ParadeSession)
            .filter(
                ParadeSession.unit_id == cadet.unit_id,
                ParadeSession.date >= leave.start_date,
                ParadeSession.date <= leave.end_date,
            )
            .all()
        )

        for parade in overlapping_parades:
            # Check squad scope of the parade
            if parade.squad_id and parade.squad_id != cadet.squad_id:
                continue

            existing_record = (
                db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.session_id == parade.id,
                    AttendanceRecord.cadet_id == cadet.id,
                )
                .first()
            )

            if existing_record:
                existing_record.status = PresenceStatus.ON_LEAVE
                existing_record.remarks = "Approved Leave"
                db.add(existing_record)
            else:
                new_record = AttendanceRecord(
                    session_id=parade.id,
                    cadet_id=cadet.id,
                    status=PresenceStatus.ON_LEAVE,
                    remarks="Approved Leave",
                    recorded_by_id=user.id,
                )
                db.add(new_record)

    audit = AuditLog(
        actor_id=user.id,
        action="LEAVE_APPROVED",
        resource_type="LeaveRequest",
        resource_id=str(leave.id),
        previous_state=prev_state,
        new_state=LeaveStatus.APPROVED.value,
        reason=data.notes or "Leave approved with attendance presence synchronization",
    )
    db.add(audit)
    db.flush()

    return map_leave_response(leave)


def reject_leave_request(
    db: Session,
    user: User,
    leave_id: int,
    data: LeaveRejectRequest,
) -> LeaveResponse:
    """Reject a leave request with mandatory rejection reason."""
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found",
        )

    if leave.status in (LeaveStatus.APPROVED, LeaveStatus.REJECTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject leave request already in status {leave.status.value}",
        )

    # Leader scope check
    cadet = leave.cadet
    if user.role == Role.LEADER and (not cadet or cadet.squad_id != user.squad_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Leaders may only reject leave requests for cadets in their squad",
        )

    prev_state = leave.status.value
    leave.status = LeaveStatus.REJECTED
    leave.rejection_reason = data.rejection_reason
    db.add(leave)

    audit = AuditLog(
        actor_id=user.id,
        action="LEAVE_REJECTED",
        resource_type="LeaveRequest",
        resource_id=str(leave.id),
        previous_state=prev_state,
        new_state=LeaveStatus.REJECTED.value,
        reason=f"Rejected: {data.rejection_reason}",
    )
    db.add(audit)
    db.flush()

    return map_leave_response(leave)
