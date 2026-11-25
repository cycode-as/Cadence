"""SQLAlchemy data models for Cadence NCC Operations Management Platform."""

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.session import Base


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    """Generate a random UUID string."""
    return str(uuid.uuid4())


class Role(str, enum.Enum):
    """User roles within the NCC operational hierarchy."""

    CO = "CO"
    ANO = "ANO"
    JUO = "JUO"
    LEADER = "Leader"
    CADET = "Cadet"


class AttendanceStatus(str, enum.Enum):
    """Lifecycle states of an attendance session."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    JUO_REVIEWED = "JUO_REVIEWED"
    ANO_APPROVED = "ANO_APPROVED"
    LOCKED = "LOCKED"


class PresenceStatus(str, enum.Enum):
    """Individual cadet presence status for a parade/session."""

    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    ON_LEAVE = "ON_LEAVE"
    EXCUSED = "EXCUSED"


class LeaveStatus(str, enum.Enum):
    """Status of a cadet leave request."""

    PENDING = "PENDING"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class TaskStatus(str, enum.Enum):
    """Status of an assigned task."""

    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"


class OtpPurpose(str, enum.Enum):
    """Agreed OTP purposes."""

    EMAIL_MFA = "EMAIL_MFA"
    PASSWORD_RESET = "PASSWORD_RESET"


class Unit(Base):
    """NCC Unit model."""

    __tablename__ = "units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    squads: Mapped[list["Squad"]] = relationship("Squad", back_populates="unit")
    users: Mapped[list["User"]] = relationship("User", back_populates="unit")


class Squad(Base):
    """Squad within an NCC Unit."""

    __tablename__ = "squads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("units.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    unit: Mapped["Unit"] = relationship("Unit", back_populates="squads")
    cadets: Mapped[list["User"]] = relationship("User", back_populates="squad")


class User(Base):
    """User account model for cadets, leaders, and officers."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    cadet_number: Mapped[str | None] = mapped_column(
        String(50), unique=True, index=True, nullable=True
    )
    rank: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role: Mapped[Role] = mapped_column(
        Enum(Role), default=Role.CADET, nullable=False, index=True
    )
    unit_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("units.id"), nullable=True, index=True
    )
    squad_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("squads.id"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )

    unit: Mapped[Optional["Unit"]] = relationship("Unit", back_populates="users")
    squad: Mapped[Optional["Squad"]] = relationship("Squad", back_populates="cadets")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    otp_codes: Mapped[list["OtpCode"]] = relationship(
        "OtpCode", back_populates="user", cascade="all, delete-orphan"
    )


class RefreshToken(Base):
    """Stored refresh tokens for rotation, revocation, and device tracking (M3 aligned)."""

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_uuid, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    unit_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("units.id"), nullable=True
    )
    contingent_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    token_hash: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    replaced_by_token_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")


class OtpCode(Base):
    """OTP codes for Email MFA and Password Reset (M3 aligned)."""

    __tablename__ = "otp_codes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_uuid, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    unit_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("units.id"), nullable=True
    )
    contingent_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )

    user: Mapped["User"] = relationship("User", back_populates="otp_codes")


class ParadeSession(Base):
    """Parade / Attendance Session."""

    __tablename__ = "parade_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("units.id"), nullable=False, index=True
    )
    squad_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("squads.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus), default=AttendanceStatus.DRAFT, nullable=False
    )
    created_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )

    records: Mapped[list["AttendanceRecord"]] = relationship(
        "AttendanceRecord", back_populates="session", cascade="all, delete-orphan"
    )


class AttendanceRecord(Base):
    """Individual cadet attendance record for a parade session."""

    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("parade_sessions.id"), nullable=False, index=True
    )
    cadet_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    status: Mapped[PresenceStatus] = mapped_column(
        Enum(PresenceStatus), default=PresenceStatus.PRESENT, nullable=False
    )
    remarks: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recorded_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )

    session: Mapped["ParadeSession"] = relationship(
        "ParadeSession", back_populates="records"
    )
    cadet: Mapped["User"] = relationship("User", foreign_keys=[cadet_id])


class LeaveRequest(Base):
    """Cadet leave request model."""

    __tablename__ = "leave_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cadet_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[LeaveStatus] = mapped_column(
        Enum(LeaveStatus), default=LeaveStatus.PENDING, nullable=False
    )
    reviewed_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    approved_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )

    cadet: Mapped["User"] = relationship("User", foreign_keys=[cadet_id])


class Notice(Base):
    """Notice bulletin model."""

    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("units.id"), nullable=False, index=True
    )
    target_squad_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("squads.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )

    author: Mapped["User"] = relationship("User", foreign_keys=[author_id])


class Task(Base):
    """Task assigned to a cadet or squad."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("units.id"), nullable=False, index=True
    )
    squad_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("squads.id"), nullable=True, index=True
    )
    assignee_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.ASSIGNED, nullable=False
    )
    submission_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )

    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])
    assignee: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[assignee_id]
    )


class AuditLog(Base):
    """Immutable audit trail for all operational state changes and sensitive actions."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    previous_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False, index=True
    )

    actor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[actor_id])
