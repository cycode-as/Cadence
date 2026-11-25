"""Pydantic schemas for Notices management."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NoticeCreateRequest(BaseModel):
    """Payload to create a new notice."""

    title: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=5)
    target_squad_id: int | None = None
    is_published: bool = True


class NoticeUpdateRequest(BaseModel):
    """Payload to update an existing notice."""

    title: str | None = Field(None, min_length=3, max_length=200)
    content: str | None = Field(None, min_length=5)
    target_squad_id: int | None = None
    is_published: bool | None = None


class NoticeResponse(BaseModel):
    """Notice response payload."""

    id: int
    unit_id: int
    target_squad_id: int | None = None
    title: str
    content: str
    author_id: int
    author_name: str | None = None
    is_published: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
