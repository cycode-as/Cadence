"""Pydantic schemas for Leave Management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.models import LeaveStatus


class LeaveCreateRequest(BaseModel):
    """Payload to submit a leave request."""

    start_date: datetime
    end_date: datetime
    reason: str = Field(min_length=5, max_length=1000)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be greater than or equal to start_date")
        return self


class LeaveReviewRequest(BaseModel):
    """Payload for reviewing a leave request."""

    notes: str | None = None


class LeaveApproveRequest(BaseModel):
    """Payload for approving a leave request."""

    notes: str | None = None


class LeaveRejectRequest(BaseModel):
    """Payload for rejecting a leave request."""

    rejection_reason: str = Field(
        min_length=5, description="Mandatory reason explaining why the leave was rejected"
    )


class LeaveResponse(BaseModel):
    """Leave request response structure."""

    id: int
    cadet_id: int
    cadet_name: str | None = None
    cadet_number: str | None = None
    squad_id: int | None = None
    start_date: datetime
    end_date: datetime
    reason: str
    status: LeaveStatus
    reviewed_by_id: int | None = None
    approved_by_id: int | None = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
