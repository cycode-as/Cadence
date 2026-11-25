"""Attendance SQLAlchemy models: parade, attendance_sheet, attendance_record."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.models.enums import (
    AttendanceStatus,
    SheetStatus,
    attendance_status_enum,
    sheet_status_enum,
)

if TYPE_CHECKING:
    from database.models.org import Squad
    from database.models.people import CadetProfile, User


class Parade(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Scheduled NCC parade event."""

    __tablename__ = "parade"

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
    company_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("company.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    parade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="RESTRICT"),
        nullable=False,
    )

    created_by: Mapped[User] = relationship("User", foreign_keys=[created_by_id])
    sheets: Mapped[list[AttendanceSheet]] = relationship(
        "AttendanceSheet",
        back_populates="parade",
        foreign_keys="AttendanceSheet.parade_id",
    )


class AttendanceSheet(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Squad-level attendance sheet for a parade with optimistic version locking."""

    __tablename__ = "attendance_sheet"
    __table_args__ = (
        UniqueConstraint("parade_id", "squad_id", name="uq_attendance_sheet_parade_squad"),
        CheckConstraint("version >= 1", name="sheet_version_positive"),
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
    parade_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("parade.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    squad_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("squad.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    status: Mapped[SheetStatus] = mapped_column(
        sheet_status_enum,
        nullable=False,
        default=SheetStatus.DRAFT,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    submitted_by_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    parade: Mapped[Parade] = relationship(
        "Parade",
        back_populates="sheets",
        foreign_keys=[parade_id],
    )
    squad: Mapped[Squad] = relationship("Squad", foreign_keys=[squad_id])
    records: Mapped[list[AttendanceRecord]] = relationship(
        "AttendanceRecord",
        back_populates="sheet",
        foreign_keys="AttendanceRecord.sheet_id",
    )


class AttendanceRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-cadet attendance entry inside an AttendanceSheet."""

    __tablename__ = "attendance_record"
    __table_args__ = (
        UniqueConstraint("sheet_id", "cadet_id", name="uq_attendance_record_sheet_cadet"),
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
    # RESTRICT protects historical attendance records from accidental deletion.
    sheet_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("attendance_sheet.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cadet_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("cadet_profile.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    status: Mapped[AttendanceStatus] = mapped_column(
        attendance_status_enum,
        nullable=False,
        default=AttendanceStatus.ABSENT,
        index=True,
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    marked_by_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    marked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sheet: Mapped[AttendanceSheet] = relationship(
        "AttendanceSheet",
        back_populates="records",
        foreign_keys=[sheet_id],
    )
    cadet: Mapped[CadetProfile] = relationship("CadetProfile", foreign_keys=[cadet_id])
    marked_by: Mapped[User | None] = relationship("User", foreign_keys=[marked_by_id])


__all__ = ["AttendanceRecord", "AttendanceSheet", "Parade"]
