"""Reporting and Analytics service providing aggregated metrics and CSV export."""

import csv
import io

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.models import (
    AttendanceRecord,
    LeaveRequest,
    LeaveStatus,
    ParadeSession,
    PresenceStatus,
    Role,
    Squad,
    Task,
    TaskStatus,
    User,
)
from modules.reports.schemas import (
    AttendanceSummaryResponse,
    CadetParticipationItem,
    LeaveSummaryResponse,
    ParticipationReportResponse,
    SquadAttendanceStat,
)


def get_attendance_summary(db: Session, user: User) -> AttendanceSummaryResponse:
    """Compute aggregated attendance metrics for unit or squad."""
    query = (
        db.query(AttendanceRecord)
        .join(ParadeSession, AttendanceRecord.session_id == ParadeSession.id)
        .filter(ParadeSession.unit_id == user.unit_id)
    )

    if user.role == Role.CADET:
        query = query.filter(AttendanceRecord.cadet_id == user.id)
    elif user.role == Role.LEADER and user.squad_id:
        query = query.join(User, AttendanceRecord.cadet_id == User.id).filter(
            User.squad_id == user.squad_id
        )

    records = query.all()
    total = len(records)
    present = sum(1 for r in records if r.status == PresenceStatus.PRESENT)
    absent = sum(1 for r in records if r.status == PresenceStatus.ABSENT)
    on_leave = sum(1 for r in records if r.status == PresenceStatus.ON_LEAVE)
    rate = round((present / total * 100.0), 2) if total > 0 else 0.0

    # Total unique parades count
    parades_count = (
        db.query(func.count(ParadeSession.id))
        .filter(ParadeSession.unit_id == user.unit_id)
        .scalar()
        or 0
    )

    # Squad-level breakdown (for Officers and Leaders)
    squad_stats = []
    if user.role in (Role.CO, Role.ANO, Role.JUO, Role.LEADER):
        squads = db.query(Squad).filter(Squad.unit_id == user.unit_id).all()
        for squad in squads:
            if user.role == Role.LEADER and squad.id != user.squad_id:
                continue
            squad_records = (
                db.query(AttendanceRecord)
                .join(User, AttendanceRecord.cadet_id == User.id)
                .join(ParadeSession, AttendanceRecord.session_id == ParadeSession.id)
                .filter(User.squad_id == squad.id, ParadeSession.unit_id == user.unit_id)
                .all()
            )
            s_total = len(squad_records)
            s_present = sum(1 for r in squad_records if r.status == PresenceStatus.PRESENT)
            s_absent = sum(1 for r in squad_records if r.status == PresenceStatus.ABSENT)
            s_leave = sum(1 for r in squad_records if r.status == PresenceStatus.ON_LEAVE)
            s_rate = round((s_present / s_total * 100.0), 2) if s_total > 0 else 0.0
            squad_stats.append(
                SquadAttendanceStat(
                    squad_id=squad.id,
                    squad_name=squad.name,
                    total_records=s_total,
                    present_count=s_present,
                    absent_count=s_absent,
                    on_leave_count=s_leave,
                    attendance_rate=s_rate,
                )
            )

    return AttendanceSummaryResponse(
        unit_id=user.unit_id,
        total_parades=parades_count,
        total_records=total,
        present_count=present,
        absent_count=absent,
        on_leave_count=on_leave,
        attendance_rate=rate,
        squad_summaries=squad_stats,
    )


def get_leave_summary(db: Session, user: User) -> LeaveSummaryResponse:
    """Compute leave statistics aggregation."""
    query = db.query(LeaveRequest).join(User, LeaveRequest.cadet_id == User.id)

    if user.role == Role.CADET:
        query = query.filter(LeaveRequest.cadet_id == user.id)
    elif user.role == Role.LEADER and user.squad_id:
        query = query.filter(User.squad_id == user.squad_id)
    elif user.role in (Role.CO, Role.ANO, Role.JUO) and user.unit_id:
        query = query.filter(User.unit_id == user.unit_id)

    leaves = query.all()
    total = len(leaves)
    pending = sum(1 for req in leaves if req.status == LeaveStatus.PENDING)
    reviewed = sum(1 for req in leaves if req.status == LeaveStatus.REVIEWED)
    approved = sum(1 for req in leaves if req.status == LeaveStatus.APPROVED)
    rejected = sum(1 for req in leaves if req.status == LeaveStatus.REJECTED)

    return LeaveSummaryResponse(
        total_requests=total,
        pending_count=pending,
        reviewed_count=reviewed,
        approved_count=approved,
        rejected_count=rejected,
    )


def get_participation_report(db: Session, user: User) -> ParticipationReportResponse:
    """Generate per-cadet participation report."""
    query = db.query(User).filter(User.unit_id == user.unit_id, User.role == Role.CADET)

    if user.role == Role.CADET:
        query = query.filter(User.id == user.id)
    elif user.role == Role.LEADER and user.squad_id:
        query = query.filter(User.squad_id == user.squad_id)

    cadets = query.all()
    total_unit_parades = (
        db.query(func.count(ParadeSession.id))
        .filter(ParadeSession.unit_id == user.unit_id)
        .scalar()
        or 0
    )

    items = []
    for cadet in cadets:
        attended = (
            db.query(func.count(AttendanceRecord.id))
            .filter(
                AttendanceRecord.cadet_id == cadet.id,
                AttendanceRecord.status == PresenceStatus.PRESENT,
            )
            .scalar()
            or 0
        )
        rate = (
            round((attended / total_unit_parades * 100.0), 2)
            if total_unit_parades > 0
            else 0.0
        )
        tasks_done = (
            db.query(func.count(Task.id))
            .filter(
                Task.assignee_id == cadet.id,
                Task.status.in_([TaskStatus.COMPLETED, TaskStatus.APPROVED]),
            )
            .scalar()
            or 0
        )

        items.append(
            CadetParticipationItem(
                cadet_id=cadet.id,
                full_name=cadet.full_name,
                cadet_number=cadet.cadet_number,
                rank=cadet.rank,
                squad_name=cadet.squad.name if cadet.squad else None,
                parades_attended=attended,
                total_parades=total_unit_parades,
                attendance_rate=rate,
                tasks_completed=tasks_done,
            )
        )

    return ParticipationReportResponse(
        unit_id=user.unit_id,
        total_cadets=len(cadets),
        cadets=items,
    )


def export_attendance_csv(db: Session, user: User) -> str:
    """Export attendance data as a sanitized, structured CSV string."""
    query = (
        db.query(AttendanceRecord)
        .join(ParadeSession, AttendanceRecord.session_id == ParadeSession.id)
        .join(User, AttendanceRecord.cadet_id == User.id)
        .filter(ParadeSession.unit_id == user.unit_id)
    )

    if user.role == Role.CADET:
        query = query.filter(AttendanceRecord.cadet_id == user.id)
    elif user.role == Role.LEADER and user.squad_id:
        query = query.filter(User.squad_id == user.squad_id)

    records = query.order_by(ParadeSession.date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow([
        "Parade Title",
        "Date",
        "Cadet Regt Number",
        "Cadet Name",
        "Squad",
        "Attendance Status",
        "Remarks",
    ])

    for r in records:
        writer.writerow([
            r.session.title if r.session else "N/A",
            r.session.date.strftime("%Y-%m-%d %H:%M") if r.session else "N/A",
            r.cadet.cadet_number if r.cadet else "N/A",
            r.cadet.full_name if r.cadet else "N/A",
            r.cadet.squad.name if r.cadet and r.cadet.squad else "N/A",
            r.status.value,
            r.remarks or "",
        ])

    return output.getvalue()
