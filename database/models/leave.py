"""Leave SQLAlchemy models: leave_request, approval_step."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.models.enums import LeaveStatus, leave_status_enum

if TYPE_CHECKING:
    from database.models.people import CadetProfile, User


class LeaveRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Cadet leave application routed through multi-level approval."""

    __tablename__ = "leave_request"
    __table_args__ = (
        CheckConstraint("to_date >= from_date", name="leave_dates_valid"),
        CheckConstraint("version >= 1", name="leave_version_positive"),
    )

    unit_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("unit.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    contingent_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("contingent.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("company.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    squad_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("squad.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cadet_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("cadet_profile.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    from_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    to_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[LeaveStatus] = mapped_column(
        leave_status_enum,
        nullable=False,
        default=LeaveStatus.PENDING_LEADER,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    decided_by_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    cadet: Mapped[CadetProfile] = relationship("CadetProfile", foreign_keys=[cadet_id])
    decided_by: Mapped[User | None] = relationship("User", foreign_keys=[decided_by_id])
    approval_steps: Mapped[list[ApprovalStep]] = relationship(
        "ApprovalStep",
        back_populates="leave_request",
        foreign_keys="ApprovalStep.leave_request_id",
        order_by="ApprovalStep.created_at",
    )


class ApprovalStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Timeline entry for each forward/escalate/decide/cancel action on a LeaveRequest."""

    __tablename__ = "approval_step"

    unit_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("unit.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    contingent_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("contingent.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    leave_request_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("leave_request.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    action: Mapped[str] = mapped_column(String(32), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    leave_request: Mapped[LeaveRequest] = relationship(
        "LeaveRequest",
        back_populates="approval_steps",
        foreign_keys=[leave_request_id],
    )
    actor: Mapped[User] = relationship("User", foreign_keys=[actor_id])


__all__ = ["ApprovalStep", "LeaveRequest"]
