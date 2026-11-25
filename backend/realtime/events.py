"""Realtime event constants for Cadence NCC Platform."""

import enum


class EventType(str, enum.Enum):
    """Event types defined in Cadence SPEC."""

    # Attendance events
    ATTENDANCE_CREATED = "attendance.created"
    ATTENDANCE_SUBMITTED = "attendance.submitted"
    ATTENDANCE_REVIEWED = "attendance.reviewed"
    ATTENDANCE_APPROVED = "attendance.approved"
    ATTENDANCE_LOCKED = "attendance.locked"

    # Leave events
    LEAVE_SUBMITTED = "leave.submitted"
    LEAVE_REVIEWED = "leave.reviewed"
    LEAVE_APPROVED = "leave.approved"
    LEAVE_REJECTED = "leave.rejected"

    # Notice events
    NOTICE_CREATED = "notice.created"

    # Task events
    TASK_ASSIGNED = "task.assigned"
    TASK_UPDATED = "task.updated"
