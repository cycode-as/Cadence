"""Pydantic schemas for Reports and Analytics."""


from pydantic import BaseModel


class SquadAttendanceStat(BaseModel):
    """Squad-level attendance aggregation."""

    squad_id: int | None = None
    squad_name: str
    total_records: int
    present_count: int
    absent_count: int
    on_leave_count: int
    attendance_rate: float


class AttendanceSummaryResponse(BaseModel):
    """Battalion/unit attendance summary report."""

    unit_id: int | None = None
    total_parades: int
    total_records: int
    present_count: int
    absent_count: int
    on_leave_count: int
    attendance_rate: float
    squad_summaries: list[SquadAttendanceStat] = []


class LeaveSummaryResponse(BaseModel):
    """Leave statistics aggregation."""

    total_requests: int
    pending_count: int
    reviewed_count: int
    approved_count: int
    rejected_count: int


class CadetParticipationItem(BaseModel):
    """Individual cadet participation performance metrics."""

    cadet_id: int
    full_name: str
    cadet_number: str | None = None
    rank: str | None = None
    squad_name: str | None = None
    parades_attended: int
    total_parades: int
    attendance_rate: float
    tasks_completed: int


class ParticipationReportResponse(BaseModel):
    """Battalion participation report."""

    unit_id: int | None = None
    total_cadets: int
    cadets: list[CadetParticipationItem] = []
