"""Communication SQLAlchemy models: notice, notice_receipt."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now
from database.models.enums import ScopeType, scope_type_enum

if TYPE_CHECKING:
    from database.models.people import User


class Notice(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Scoped or public announcement notice."""

    __tablename__ = "notice"

    unit_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("unit.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Nullable when target_scope_type is BATTALION or public unit-wide notice.
    contingent_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("contingent.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    author_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    target_scope_type: Mapped[ScopeType] = mapped_column(
        scope_type_enum,
        nullable=False,
        index=True,
    )
    target_scope_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False, index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    author: Mapped[User] = relationship("User", foreign_keys=[author_id])
    receipts: Mapped[list[NoticeReceipt]] = relationship(
        "NoticeReceipt",
        back_populates="notice",
        foreign_keys="NoticeReceipt.notice_id",
        cascade="all, delete-orphan",
    )


class NoticeReceipt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-user read receipt for a Notice."""

    __tablename__ = "notice_receipt"
    __table_args__ = (
        UniqueConstraint("notice_id", "user_id", name="uq_notice_receipt_notice_user"),
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
    notice_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("notice.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    notice: Mapped[Notice] = relationship(
        "Notice",
        back_populates="receipts",
        foreign_keys=[notice_id],
    )
    user: Mapped[User] = relationship("User", foreign_keys=[user_id])


__all__ = ["Notice", "NoticeReceipt"]
