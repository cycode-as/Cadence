"""Pydantic schemas for Tasks management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from core.models import TaskStatus


class TaskCreateRequest(BaseModel):
    """Payload to create and assign a new task."""

    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5)
    due_date: datetime
    squad_id: int | None = None
    assignee_id: int | None = None


class TaskUpdateRequest(BaseModel):
    """Payload to update task metadata or progress."""

    title: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, min_length=5)
    due_date: datetime | None = None
    status: TaskStatus | None = None


class TaskSubmitRequest(BaseModel):
    """Payload for cadet submitting completed task work."""

    submission_text: str = Field(min_length=5, description="Details of completed work")


class TaskReviewRequest(BaseModel):
    """Payload for reviewing and approving or rejecting a task submission."""

    status: TaskStatus = Field(description="Must be COMPLETED or REJECTED")
    feedback: str | None = Field(None, description="Review feedback or rejection reason")


class TaskResponse(BaseModel):
    """Task response structure."""

    id: int
    unit_id: int
    squad_id: int | None = None
    assignee_id: int | None = None
    assignee_name: str | None = None
    title: str
    description: str
    due_date: datetime
    status: TaskStatus
    submission_text: str | None = None
    feedback: str | None = None
    created_by_id: int
    creator_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
