"""Pydantic schemas for Attendance and Parade management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from core.models import AttendanceStatus, PresenceStatus


class ParadeCreateRequest(BaseModel):
    """Payload to create a new parade or attendance session."""

    title: str = Field(min_length=3, max_length=100)
    date: datetime
    squad_id: int | None = None


class ParadeResponse(BaseModel):
    """Parade session summary."""

    id: int
    unit_id: int
    squad_id: int | None = None
    title: str
    date: datetime
    status: AttendanceStatus
    created_by_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttendanceRecordItem(BaseModel):
    """Individual cadet presence status within a submission."""

    cadet_id: int
    status: PresenceStatus
    remarks: str | None = None


class SubmitAttendanceRequest(BaseModel):
    """Payload for squad leader submitting attendance records."""

    squad_id: int | None = None
    records: list[AttendanceRecordItem] = Field(min_length=1)


class ReviewAttendanceRequest(BaseModel):
    """Payload for JUO review step."""

    notes: str | None = None


class ApproveAttendanceRequest(BaseModel):
    """Payload for ANO approval step."""

    notes: str | None = None


class CorrectRecordRequest(BaseModel):
    """Payload to correct an attendance record after locking/approval."""

    status: PresenceStatus
    reason: str = Field(min_length=5, description="Mandatory reason for audit trail")
    remarks: str | None = None


class AttendanceRecordResponse(BaseModel):
    """Individual cadet attendance record response."""

    id: int
    session_id: int
    cadet_id: int
    cadet_name: str | None = None
    cadet_number: str | None = None
    status: PresenceStatus
    remarks: str | None = None
    recorded_by_id: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ParadeDetailResponse(ParadeResponse):
    """Detailed parade session including all individual cadet records."""

    records: list[AttendanceRecordResponse] = []
