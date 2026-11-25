"""Organizational hierarchy SQLAlchemy models: unit, contingent, company, squad."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Unit(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Top-level NCC battalion / unit."""

    __tablename__ = "unit"

    # Root battalion has no parent contingent; unit_id is kept nullable at root
    # to satisfy the shared scope-column contract without an invalid self-FK.
    unit_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True, index=True)
    contingent_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    code: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)

    contingents: Mapped[list[Contingent]] = relationship(
        "Contingent",
        back_populates="unit",
        foreign_keys="Contingent.unit_id",
    )


class Contingent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """NCC contingent belonging to a unit (battalion)."""

    __tablename__ = "contingent"
    __table_args__ = (UniqueConstraint("unit_id", "name", name="uq_contingent_unit_name"),)

    unit_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False),
        ForeignKey("unit.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Scope column kept nullable on contingent itself to avoid a circular self-FK.
    contingent_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True, index=True)

    name: Mapped[str] = mapped_column(String(120), nullable=False)

    unit: Mapped[Unit] = relationship(
        "Unit",
        back_populates="contingents",
        foreign_keys=[unit_id],
    )
    companies: Mapped[list[Company]] = relationship(
        "Company",
        back_populates="contingent",
        foreign_keys="Company.contingent_id",
    )


class Company(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Company belonging to a contingent."""

    __tablename__ = "company"
    __table_args__ = (UniqueConstraint("contingent_id", "name", name="uq_company_contingent_name"),)

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

    name: Mapped[str] = mapped_column(String(120), nullable=False)

    contingent: Mapped[Contingent] = relationship(
        "Contingent",
        back_populates="companies",
        foreign_keys=[contingent_id],
    )
    squads: Mapped[list[Squad]] = relationship(
        "Squad",
        back_populates="company",
        foreign_keys="Squad.company_id",
    )


class Squad(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Squad belonging to a company."""

    __tablename__ = "squad"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_squad_company_name"),)

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

    name: Mapped[str] = mapped_column(String(120), nullable=False)

    company: Mapped[Company] = relationship(
        "Company",
        back_populates="squads",
        foreign_keys=[company_id],
    )


__all__ = ["Company", "Contingent", "Squad", "Unit"]
