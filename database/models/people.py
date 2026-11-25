"""People SQLAlchemy models: user, cadet_profile, role_assignment, rank_history."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from database.models.enums import Rank, Role, ScopeType, rank_enum, role_enum, scope_type_enum

if TYPE_CHECKING:
    from database.models.auth import OtpCode, RefreshToken
    from database.models.org import Company, Squad


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Authenticated CADENCE user account (role stored separately from cadet rank)."""

    __tablename__ = "user"

    unit_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("unit.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Nullable for battalion-wide accounts (e.g., CO).
    contingent_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("contingent.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(role_enum, nullable=False, default=Role.CADET, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    totp_secret: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    cadet_profile: Mapped[CadetProfile | None] = relationship(
        "CadetProfile",
        back_populates="user",
        uselist=False,
        foreign_keys="CadetProfile.user_id",
    )
    role_assignments: Mapped[list[RoleAssignment]] = relationship(
        "RoleAssignment",
        back_populates="user",
        foreign_keys="RoleAssignment.user_id",
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        "RefreshToken",
        back_populates="user",
        foreign_keys="RefreshToken.user_id",
        cascade="all, delete-orphan",
    )
    otp_codes: Mapped[list[OtpCode]] = relationship(
        "OtpCode",
        back_populates="user",
        foreign_keys="OtpCode.user_id",
        cascade="all, delete-orphan",
    )


class CadetProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Cadet-specific profile linked 1:1 to User."""

    __tablename__ = "cadet_profile"

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
    user_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    cadet_no: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    rank: Mapped[Rank] = mapped_column(rank_enum, nullable=False, default=Rank.CADET, index=True)
    division: Mapped[str | None] = mapped_column(String(16), nullable=True)
    enrollment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    guardian_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    guardian_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    user: Mapped[User] = relationship(
        "User",
        back_populates="cadet_profile",
        foreign_keys=[user_id],
    )
    company: Mapped[Company] = relationship("Company", foreign_keys=[company_id])
    squad: Mapped[Squad] = relationship("Squad", foreign_keys=[squad_id])
    rank_history: Mapped[list[RankHistory]] = relationship(
        "RankHistory",
        back_populates="cadet",
        foreign_keys="RankHistory.cadet_id",
        order_by="RankHistory.created_at",
    )


class RoleAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Scoped role assignment record for authorization and delegation."""

    __tablename__ = "role_assignment"
    __table_args__ = (Index("ix_role_assignment_user_active", "user_id", "is_active"),)

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
    role: Mapped[Role] = mapped_column(role_enum, nullable=False, index=True)
    scope_type: Mapped[ScopeType] = mapped_column(scope_type_enum, nullable=False)
    scope_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False, index=True)
    assigned_by_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped[User] = relationship(
        "User",
        back_populates="role_assignments",
        foreign_keys=[user_id],
    )
    assigned_by: Mapped[User | None] = relationship("User", foreign_keys=[assigned_by_id])


class RankHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable log of rank changes for a cadet."""

    __tablename__ = "rank_history"

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
    cadet_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("cadet_profile.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    from_rank: Mapped[Rank | None] = mapped_column(rank_enum, nullable=True)
    to_rank: Mapped[Rank] = mapped_column(rank_enum, nullable=False)
    changed_by_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("user.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    cadet: Mapped[CadetProfile] = relationship(
        "CadetProfile",
        back_populates="rank_history",
        foreign_keys=[cadet_id],
    )
    changed_by: Mapped[User] = relationship("User", foreign_keys=[changed_by_id])


__all__ = ["CadetProfile", "RankHistory", "RoleAssignment", "User"]
