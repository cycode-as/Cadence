"""Authentication SQLAlchemy models requested by Member 1: refresh_token, otp_code."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, new_uuid

if TYPE_CHECKING:
    from database.models.people import User


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Hashed rotating refresh token store (never stores raw tokens)."""

    __tablename__ = "refresh_token"
    __table_args__ = (Index("ix_refresh_token_user_family", "user_id", "family_id"),)

    unit_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("unit.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Nullable for battalion-level users (e.g., CO).
    contingent_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("contingent.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    # Additional field to group rotated refresh tokens for reuse detection.
    family_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        nullable=False,
        default=new_uuid,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_token_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("refresh_token.id", ondelete="SET NULL"),
        nullable=True,
    )

    user: Mapped[User] = relationship(
        "User",
        back_populates="refresh_tokens",
        foreign_keys=[user_id],
    )
    replaced_by: Mapped[RefreshToken | None] = relationship(
        "RefreshToken",
        remote_side="RefreshToken.id",
        foreign_keys=[replaced_by_token_id],
        uselist=False,
    )


class OtpCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Hashed one-time email OTP code with expiry and failed-attempt tracking."""

    __tablename__ = "otp_code"
    __table_args__ = (
        CheckConstraint("attempt_count >= 0", name="attempt_count_non_negative"),
        Index("ix_otp_code_user_purpose_expires", "user_id", "purpose", "expires_at"),
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
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, default="mfa_email")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user: Mapped[User] = relationship(
        "User",
        back_populates="otp_codes",
        foreign_keys=[user_id],
    )


__all__ = ["OtpCode", "RefreshToken"]
