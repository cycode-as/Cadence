"""Other CADENCE SQLAlchemy models: exam_resource, audit_log."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now
from database.models.enums import ExamLevel, exam_level_enum

if TYPE_CHECKING:
    from database.models.people import User

JSONVariant = JSON().with_variant(JSONB(), "postgresql")


class ExamResource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """External study link grouped by NCC certificate level (A/B/C)."""

    __tablename__ = "exam_resource"

    unit_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("unit.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Nullable when shared unit-wide or visible to guests.
    contingent_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("contingent.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[ExamLevel] = mapped_column(exam_level_enum, nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_by_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="RESTRICT"),
        nullable=False,
    )

    created_by: Mapped[User] = relationship("User", foreign_keys=[created_by_id])


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """Append-only audit trail for sensitive mutations across CADENCE."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_entity", "entity_type", "entity_id"),)

    unit_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("unit.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Nullable for battalion-wide / CO actions; ANO queries filter by own contingent_id.
    contingent_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("contingent.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    actor_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False, index=True)
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSONVariant, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Append-only: updated_at is stored at insert time without onupdate mutation.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )

    actor: Mapped[User | None] = relationship("User", foreign_keys=[actor_id])


__all__ = ["AuditLog", "ExamResource"]
