"""Task SQLAlchemy model for scoped work items."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from database.models.org import Contingent, Squad, Unit
    from database.models.people import User


class Task(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Work item scoped to a unit and optionally a contingent or squad."""

    __tablename__ = "task"
    __table_args__ = (
        CheckConstraint(
            "status IN ('TODO', 'IN_PROGRESS', 'DONE', 'CANCELLED')",
            name="task_status_valid",
        ),
        CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'URGENT')",
            name="task_priority_valid",
        ),
    )

    unit_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("unit.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    contingent_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("contingent.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    squad_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("squad.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    created_by_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assignee_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="TODO", index=True)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="MEDIUM", index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)

    unit: Mapped[Unit] = relationship("Unit", foreign_keys=[unit_id])
    contingent: Mapped[Contingent | None] = relationship("Contingent", foreign_keys=[contingent_id])
    squad: Mapped[Squad | None] = relationship("Squad", foreign_keys=[squad_id])
    creator: Mapped[User] = relationship("User", foreign_keys=[created_by_id])
    assignee: Mapped[User | None] = relationship("User", foreign_keys=[assignee_id])


__all__ = ["Task"]
