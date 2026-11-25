"""Attendance management service implementing state transitions and audit logging."""


from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.models import (
    AttendanceRecord,
    AttendanceStatus,
    AuditLog,
    ParadeSession,
    Role,
    User,
)
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
from policy.permissions import enforce_scope


def create_parade(
    db: Session,
    user: User,
    data: ParadeCreateRequest,
) -> ParadeResponse:
    """Create a new parade or attendance session in DRAFT status."""
    enforce_scope(user, target_unit_id=user.unit_id, target_squad_id=data.squad_id)

    parade = ParadeSession(
        unit_id=user.unit_id or 1,
        squad_id=data.squad_id,
        title=data.title,
        date=data.date,
        status=AttendanceStatus.DRAFT,
        created_by_id=user.id,
    )
    db.add(parade)
    db.flush()

    # Transaction-consistent audit record
    audit = AuditLog(
        actor_id=user.id,
        action="ATTENDANCE_SESSION_CREATED",
        resource_type="ParadeSession",
        resource_id=str(parade.id),
        new_state=AttendanceStatus.DRAFT.value,
        reason=f"Parade session '{parade.title}' created",
    )
    db.add(audit)
    db.flush()

    return ParadeResponse.model_validate(parade)


def get_parades(
    db: Session,
    user: User,
    status_filter: AttendanceStatus | None = None,
) -> list[ParadeResponse]:
    """List parades filtered by user scope and optional status."""
    query = db.query(ParadeSession).filter(ParadeSession.unit_id == user.unit_id)

    # Scoped visibility for Leader and Cadet
    if user.role in (Role.LEADER, Role.CADET) and user.squad_id:
        query = query.filter(
            (ParadeSession.squad_id == user.squad_id) | (ParadeSession.squad_id.is_(None))
        )

    if status_filter:
        query = query.filter(ParadeSession.status == status_filter)

    parades = query.order_by(ParadeSession.date.desc()).all()
    return [ParadeResponse.model_validate(p) for p in parades]


def get_parade_detail(
    db: Session,
    user: User,
    parade_id: int,
) -> ParadeDetailResponse:
    """Get complete parade details with all associated cadet attendance records."""
    parade = db.query(ParadeSession).filter(ParadeSession.id == parade_id).first()
    if not parade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parade session not found",
        )

    if user.role == Role.CADET:
        if user.unit_id != parade.unit_id or (
            parade.squad_id and user.squad_id != parade.squad_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Parade is outside your assigned unit/squad",
            )
    else:
        enforce_scope(user, target_unit_id=parade.unit_id, target_squad_id=parade.squad_id)

    records = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.session_id == parade.id)
        .all()
    )

    record_responses = []
    for r in records:
        # Cadets can only see their own attendance record within a parade
        if user.role == Role.CADET and r.cadet_id != user.id:
            continue
        record_responses.append(
            AttendanceRecordResponse(
                id=r.id,
                session_id=r.session_id,
                cadet_id=r.cadet_id,
                cadet_name=r.cadet.full_name if r.cadet else None,
                cadet_number=r.cadet.cadet_number if r.cadet else None,
                status=r.status,
                remarks=r.remarks,
                recorded_by_id=r.recorded_by_id,
                updated_at=r.updated_at,
            )
        )

    response = ParadeDetailResponse.model_validate(parade)
    response.records = record_responses
    return response


def submit_squad_attendance(
    db: Session,
    user: User,
    parade_id: int,
    data: SubmitAttendanceRequest,
) -> ParadeDetailResponse:
    """Submit squad-level attendance entries (DRAFT/SUBMITTED -> SUBMITTED)."""
    parade = db.query(ParadeSession).filter(ParadeSession.id == parade_id).first()
    if not parade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parade session not found",
        )

    if parade.status not in (AttendanceStatus.DRAFT, AttendanceStatus.SUBMITTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit attendance when status is {parade.status.value}",
        )

    # Leader can only submit for their assigned squad
    if user.role == Role.LEADER:
        if data.squad_id and data.squad_id != user.squad_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Leaders may only submit attendance for their assigned squad",
            )

    # Collect existing cadet IDs to prevent duplicate attendance records
    existing_records = (
        db.query(AttendanceRecord.cadet_id)
        .filter(AttendanceRecord.session_id == parade.id)
        .all()
    )
    existing_cadet_ids = {row[0] for row in existing_records}

    for item in data.records:
        cadet = db.query(User).filter(User.id == item.cadet_id).first()
        if not cadet:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cadet ID {item.cadet_id} does not exist",
            )

        # Leader scope: verify cadet belongs to the leader's squad
        if user.role == Role.LEADER and cadet.squad_id != user.squad_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cadet {cadet.full_name} does not belong to your squad",
            )

        if item.cadet_id in existing_cadet_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Duplicate attendance record for cadet ID {item.cadet_id}",
            )

        record = AttendanceRecord(
            session_id=parade.id,
            cadet_id=item.cadet_id,
            status=item.status,
            remarks=item.remarks,
            recorded_by_id=user.id,
        )
        db.add(record)
        existing_cadet_ids.add(item.cadet_id)

    prev_state = parade.status.value
    parade.status = AttendanceStatus.SUBMITTED
    db.add(parade)

    # Audit log entry
    audit = AuditLog(
        actor_id=user.id,
        action="ATTENDANCE_SUBMITTED",
        resource_type="ParadeSession",
        resource_id=str(parade.id),
        previous_state=prev_state,
        new_state=AttendanceStatus.SUBMITTED.value,
        reason=f"Attendance submitted with {len(data.records)} records",
    )
    db.add(audit)
    db.flush()

    return get_parade_detail(db, user, parade.id)


def review_attendance(
    db: Session,
    user: User,
    parade_id: int,
    data: ReviewAttendanceRequest,
) -> ParadeResponse:
    """Transition parade attendance: SUBMITTED -> JUO_REVIEWED."""
    parade = db.query(ParadeSession).filter(ParadeSession.id == parade_id).first()
    if not parade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parade session not found",
        )

    if parade.status != AttendanceStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expected SUBMITTED status for JUO review, got {parade.status.value}",
        )

    prev_state = parade.status.value
    parade.status = AttendanceStatus.JUO_REVIEWED
    db.add(parade)

    audit = AuditLog(
        actor_id=user.id,
        action="ATTENDANCE_REVIEWED",
        resource_type="ParadeSession",
        resource_id=str(parade.id),
        previous_state=prev_state,
        new_state=AttendanceStatus.JUO_REVIEWED.value,
        reason=data.notes or "JUO reviewed squad attendance",
    )
    db.add(audit)
    db.flush()

    return ParadeResponse.model_validate(parade)


def approve_attendance(
    db: Session,
    user: User,
    parade_id: int,
    data: ApproveAttendanceRequest,
) -> ParadeResponse:
    """Transition parade attendance: JUO_REVIEWED -> ANO_APPROVED."""
    parade = db.query(ParadeSession).filter(ParadeSession.id == parade_id).first()
    if not parade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parade session not found",
        )

    if parade.status != AttendanceStatus.JUO_REVIEWED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expected JUO_REVIEWED status for ANO approval, got {parade.status.value}",
        )

    prev_state = parade.status.value
    parade.status = AttendanceStatus.ANO_APPROVED
    db.add(parade)

    audit = AuditLog(
        actor_id=user.id,
        action="ATTENDANCE_APPROVED",
        resource_type="ParadeSession",
        resource_id=str(parade.id),
        previous_state=prev_state,
        new_state=AttendanceStatus.ANO_APPROVED.value,
        reason=data.notes or "ANO approved attendance",
    )
    db.add(audit)
    db.flush()

    return ParadeResponse.model_validate(parade)


def lock_attendance(
    db: Session,
    user: User,
    parade_id: int,
) -> ParadeResponse:
    """Transition parade attendance: ANO_APPROVED -> LOCKED."""
    parade = db.query(ParadeSession).filter(ParadeSession.id == parade_id).first()
    if not parade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Parade session not found",
        )

    if parade.status != AttendanceStatus.ANO_APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expected ANO_APPROVED status to lock attendance, got {parade.status.value}",
        )

    prev_state = parade.status.value
    parade.status = AttendanceStatus.LOCKED
    db.add(parade)

    audit = AuditLog(
        actor_id=user.id,
        action="ATTENDANCE_LOCKED",
        resource_type="ParadeSession",
        resource_id=str(parade.id),
        previous_state=prev_state,
        new_state=AttendanceStatus.LOCKED.value,
        reason="Attendance session locked for permanent records",
    )
    db.add(audit)
    db.flush()

    return ParadeResponse.model_validate(parade)


def correct_attendance_record(
    db: Session,
    user: User,
    parade_id: int,
    record_id: int,
    data: CorrectRecordRequest,
) -> AttendanceRecordResponse:
    """Apply an authorized correction to a locked/approved record with mandatory audit reason."""
    record = (
        db.query(AttendanceRecord)
        .filter(AttendanceRecord.id == record_id, AttendanceRecord.session_id == parade_id)
        .first()
    )
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found in this parade session",
        )

    prev_status = record.status.value
    record.status = data.status
    if data.remarks:
        record.remarks = data.remarks
    record.recorded_by_id = user.id
    db.add(record)

    # Mandatory reason captured in immutable audit trail
    audit = AuditLog(
        actor_id=user.id,
        action="ATTENDANCE_RECORD_CORRECTED",
        resource_type="AttendanceRecord",
        resource_id=str(record.id),
        previous_state=prev_status,
        new_state=data.status.value,
        reason=data.reason,
    )
    db.add(audit)
    db.flush()

    return AttendanceRecordResponse(
        id=record.id,
        session_id=record.session_id,
        cadet_id=record.cadet_id,
        cadet_name=record.cadet.full_name if record.cadet else None,
        cadet_number=record.cadet.cadet_number if record.cadet else None,
        status=record.status,
        remarks=record.remarks,
        recorded_by_id=record.recorded_by_id,
        updated_at=record.updated_at,
    )
