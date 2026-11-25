"""Frozen CADENCE domain enums defined strictly per docs/CONTRACTS.md."""

from __future__ import annotations

from enum import Enum

from sqlalchemy import Enum as SAEnum


class Role(str, Enum):
    """User authorization roles in CADENCE."""

    CADET = "CADET"
    CADET_LEADER = "CADET_LEADER"
    JUO = "JUO"
    ANO = "ANO"
    CO = "CO"


class Rank(str, Enum):
    """NCC cadet and officer ranks (stored separately from Role)."""

    CADET = "CADET"
    LCPL = "LCPL"
    CPL = "CPL"
    SGT = "SGT"
    CQMS = "CQMS"
    CSM = "CSM"
    JUO = "JUO"
    SUO = "SUO"
    OFFICER = "OFFICER"


class ScopeType(str, Enum):
    """Organizational visibility and targeting scopes."""

    SELF = "SELF"
    SQUAD = "SQUAD"
    COMPANY = "COMPANY"
    CONTINGENT = "CONTINGENT"
    BATTALION = "BATTALION"


class AttendanceStatus(str, Enum):
    """Per-cadet attendance status values."""

    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    LEAVE = "LEAVE"
    LATE = "LATE"


class SheetStatus(str, Enum):
    """Attendance sheet workflow state machine."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    JUO_REVIEWED = "JUO_REVIEWED"
    ANO_APPROVED = "ANO_APPROVED"
    LOCKED = "LOCKED"


class LeaveStatus(str, Enum):
    """Leave request approval workflow states."""

    PENDING_LEADER = "PENDING_LEADER"
    PENDING_JUO = "PENDING_JUO"
    PENDING_ANO = "PENDING_ANO"
    PENDING_CO = "PENDING_CO"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ExamLevel(str, Enum):
    """NCC certificate examination levels."""

    A = "A"
    B = "B"
    C = "C"


# Named SQLAlchemy Enum types for deterministic PostgreSQL/Alembic DDL.
role_enum = SAEnum(Role, name="role_enum", native_enum=True)
rank_enum = SAEnum(Rank, name="rank_enum", native_enum=True)
scope_type_enum = SAEnum(ScopeType, name="scope_type_enum", native_enum=True)
attendance_status_enum = SAEnum(AttendanceStatus, name="attendance_status_enum", native_enum=True)
sheet_status_enum = SAEnum(SheetStatus, name="sheet_status_enum", native_enum=True)
leave_status_enum = SAEnum(LeaveStatus, name="leave_status_enum", native_enum=True)
exam_level_enum = SAEnum(ExamLevel, name="exam_level_enum", native_enum=True)

ALL_ENUM_TYPES = (
    role_enum,
    rank_enum,
    scope_type_enum,
    attendance_status_enum,
    sheet_status_enum,
    leave_status_enum,
    exam_level_enum,
)

__all__ = [
    "ALL_ENUM_TYPES",
    "AttendanceStatus",
    "ExamLevel",
    "LeaveStatus",
    "Rank",
    "Role",
    "ScopeType",
    "SheetStatus",
    "attendance_status_enum",
    "exam_level_enum",
    "leave_status_enum",
    "rank_enum",
    "role_enum",
    "scope_type_enum",
    "sheet_status_enum",
]
