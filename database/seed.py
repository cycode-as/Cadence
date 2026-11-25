"""Idempotent database seed script for CADENCE.

Usage:
    python -m database.seed

Seeds:
    - 1 battalion (Unit)
    - 2 contingents
    - 4 companies (2 per contingent) and 8 squads (2 per company)
    - 60 cadets (CadetProfile + User) with distinct rank and role
    - 1 login for each contract role:
      cadet@cadence.test, leader@cadence.test, juo@cadence.test,
      ano@cadence.test, co@cadence.test
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import uuid
from datetime import date

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    CadetProfile,
    Company,
    Contingent,
    Rank,
    RankHistory,
    Role,
    RoleAssignment,
    ScopeType,
    Squad,
    Unit,
    User,
)
from database.session import SessionLocal, get_engine

SEED_NAMESPACE = uuid.UUID("7f3b8c2a-6c4d-4d8e-9a1b-2c3d4e5f6a7b")
PBKDF2_ITERATIONS = 600_000
PLACEHOLDER_PASSWORDS = {
    "",
    "REPLACE_WITH_LOCAL_DEMO_PASSWORD",
    "change-me",
    "changeme",
}

ROLE_DEFAULT_SCOPE: dict[Role, ScopeType] = {
    Role.CADET: ScopeType.SELF,
    Role.CADET_LEADER: ScopeType.SQUAD,
    Role.JUO: ScopeType.COMPANY,
    Role.ANO: ScopeType.CONTINGENT,
    Role.CO: ScopeType.BATTALION,
}


def _seed_uuid(key: str) -> str:
    """Generate a deterministic UUID string for idempotent seeding."""
    return str(uuid.uuid5(SEED_NAMESPACE, key))


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with a random 16-byte salt."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    digest_b64 = base64.b64encode(digest).decode("ascii")
    return f"$pbkdf2-sha256${PBKDF2_ITERATIONS}${salt_b64}${digest_b64}"


def resolve_seed_password() -> str:
    """Resolve demo seed password from environment without hardcoding credentials."""
    load_dotenv()
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    env_password = os.getenv("CADENCE_SEED_PASSWORD", "").strip()

    if env_password and env_password not in PLACEHOLDER_PASSWORDS:
        return env_password

    if app_env == "production":
        raise RuntimeError(
            "CADENCE_SEED_PASSWORD must be set in production environments before running seed."
        )

    # Safe local-only ephemeral fallback so no credential is hardcoded in source.
    return secrets.token_urlsafe(18)


def _get_or_create_unit(db: Session, name: str, code: str) -> Unit:
    unit = db.scalar(select(Unit).where(Unit.name == name))
    if unit is None:
        unit = Unit(id=_seed_uuid(f"unit:{name}"), name=name, code=code)
        db.add(unit)
        db.flush()
    return unit


def _get_or_create_contingent(db: Session, unit: Unit, name: str) -> Contingent:
    contingent = db.scalar(
        select(Contingent).where(Contingent.unit_id == unit.id, Contingent.name == name)
    )
    if contingent is None:
        contingent = Contingent(
            id=_seed_uuid(f"contingent:{unit.id}:{name}"),
            unit_id=unit.id,
            name=name,
        )
        db.add(contingent)
        db.flush()
    return contingent


def _get_or_create_company(db: Session, contingent: Contingent, name: str) -> Company:
    company = db.scalar(
        select(Company).where(Company.contingent_id == contingent.id, Company.name == name)
    )
    if company is None:
        company = Company(
            id=_seed_uuid(f"company:{contingent.id}:{name}"),
            unit_id=contingent.unit_id,
            contingent_id=contingent.id,
            name=name,
        )
        db.add(company)
        db.flush()
    return company


def _get_or_create_squad(db: Session, company: Company, name: str) -> Squad:
    squad = db.scalar(select(Squad).where(Squad.company_id == company.id, Squad.name == name))
    if squad is None:
        squad = Squad(
            id=_seed_uuid(f"squad:{company.id}:{name}"),
            unit_id=company.unit_id,
            contingent_id=company.contingent_id,
            company_id=company.id,
            name=name,
        )
        db.add(squad)
        db.flush()
    return squad


def _get_or_create_user(
    db: Session,
    *,
    unit_id: str,
    contingent_id: str | None,
    email: str,
    full_name: str,
    role: Role,
    password_hash: str,
    phone: str | None = None,
) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(
            id=_seed_uuid(f"user:{email}"),
            unit_id=unit_id,
            contingent_id=contingent_id,
            email=email,
            full_name=full_name,
            phone=phone,
            password_hash=password_hash,
            role=role,
            is_active=True,
            must_change_password=False,
            mfa_enabled=False,
        )
        db.add(user)
        db.flush()
    return user


def _ensure_role_assignment(
    db: Session,
    *,
    user: User,
    role: Role,
    scope_type: ScopeType,
    scope_id: str,
    assigned_by_id: str | None = None,
) -> RoleAssignment:
    assignment = db.scalar(
        select(RoleAssignment).where(
            RoleAssignment.user_id == user.id,
            RoleAssignment.role == role,
            RoleAssignment.scope_type == scope_type,
            RoleAssignment.scope_id == scope_id,
        )
    )
    if assignment is None:
        assignment = RoleAssignment(
            id=_seed_uuid(f"role_assignment:{user.id}:{role.value}:{scope_type.value}:{scope_id}"),
            unit_id=user.unit_id,
            contingent_id=user.contingent_id,
            user_id=user.id,
            role=role,
            scope_type=scope_type,
            scope_id=scope_id,
            assigned_by_id=assigned_by_id,
            is_active=True,
        )
        db.add(assignment)
        db.flush()
    return assignment


def _ensure_cadet_profile(
    db: Session,
    *,
    user: User,
    squad: Squad,
    cadet_no: str,
    rank: Rank,
    division: str,
    changed_by_id: str,
) -> CadetProfile:
    profile = db.scalar(select(CadetProfile).where(CadetProfile.user_id == user.id))
    if profile is None:
        profile = CadetProfile(
            id=_seed_uuid(f"cadet_profile:{cadet_no}"),
            unit_id=squad.unit_id,
            contingent_id=squad.contingent_id,
            company_id=squad.company_id,
            squad_id=squad.id,
            user_id=user.id,
            cadet_no=cadet_no,
            rank=rank,
            division=division,
            enrollment_date=date(2026, 7, 1),
        )
        db.add(profile)
        db.flush()

        history = RankHistory(
            id=_seed_uuid(f"rank_history:init:{cadet_no}"),
            unit_id=squad.unit_id,
            contingent_id=squad.contingent_id,
            cadet_id=profile.id,
            from_rank=None,
            to_rank=rank,
            changed_by_id=changed_by_id,
            reason="Initial seed rank assignment",
        )
        db.add(history)
        db.flush()
    return profile


def seed_database(db: Session) -> dict[str, int]:
    """Idempotently populate CADENCE demo hierarchy, logins, and 60 cadets."""
    password_hash = hash_password(resolve_seed_password())

    unit = _get_or_create_unit(db, name="1st CADENCE NCC Battalion", code="BN-01")

    contingent_alpha = _get_or_create_contingent(db, unit, "Alpha Contingent")
    contingent_bravo = _get_or_create_contingent(db, unit, "Bravo Contingent")
    contingents = [contingent_alpha, contingent_bravo]

    companies: list[Company] = []
    squads: list[Squad] = []
    for cont, comp_names in (
        (contingent_alpha, ("Alpha Coy 1", "Alpha Coy 2")),
        (contingent_bravo, ("Bravo Coy 1", "Bravo Coy 2")),
    ):
        for comp_name in comp_names:
            comp = _get_or_create_company(db, cont, comp_name)
            companies.append(comp)
            for idx in (1, 2):
                squads.append(_get_or_create_squad(db, comp, f"{comp_name} - Squad {idx}"))

    # Battalion CO & Contingent ANO logins (officer accounts without cadet profiles).
    co_user = _get_or_create_user(
        db,
        unit_id=unit.id,
        contingent_id=None,
        email="co@cadence.test",
        full_name="Commanding Officer Demo",
        role=Role.CO,
        password_hash=password_hash,
    )
    _ensure_role_assignment(
        db,
        user=co_user,
        role=Role.CO,
        scope_type=ROLE_DEFAULT_SCOPE[Role.CO],
        scope_id=unit.id,
        assigned_by_id=co_user.id,
    )

    ano_user = _get_or_create_user(
        db,
        unit_id=unit.id,
        contingent_id=contingent_alpha.id,
        email="ano@cadence.test",
        full_name="ANO Alpha Demo",
        role=Role.ANO,
        password_hash=password_hash,
    )
    _ensure_role_assignment(
        db,
        user=ano_user,
        role=Role.ANO,
        scope_type=ROLE_DEFAULT_SCOPE[Role.ANO],
        scope_id=contingent_alpha.id,
        assigned_by_id=co_user.id,
    )

    # 60 cadets distributed across the 8 squads (4x8 + 4x7 = 60).
    # First three cadets correspond to the cadet@, leader@, and juo@ role logins.
    special_cadets: dict[int, tuple[str, str, Role, Rank]] = {
        1: ("cadet@cadence.test", "Cadet Demo", Role.CADET, Rank.CADET),
        2: ("leader@cadence.test", "Cadet Leader Demo", Role.CADET_LEADER, Rank.CPL),
        3: ("juo@cadence.test", "JUO Demo", Role.JUO, Rank.JUO),
    }

    squad_distribution = [8, 8, 8, 8, 7, 7, 7, 7]
    cadet_counter = 0
    for squad_idx, count in enumerate(squad_distribution):
        squad = squads[squad_idx]
        for _ in range(count):
            cadet_counter += 1
            if cadet_counter in special_cadets:
                email, full_name, role, rank = special_cadets[cadet_counter]
            else:
                email = f"cadet{cadet_counter:03d}@cadence.test"
                full_name = f"Cadet {cadet_counter:03d}"
                role = Role.CADET
                rank = Rank.LCPL if cadet_counter % 5 == 0 else Rank.CADET

            user = _get_or_create_user(
                db,
                unit_id=squad.unit_id,
                contingent_id=squad.contingent_id,
                email=email,
                full_name=full_name,
                role=role,
                password_hash=password_hash,
            )

            scope_type = ROLE_DEFAULT_SCOPE[role]
            if scope_type == ScopeType.SELF:
                scope_id = user.id
            elif scope_type == ScopeType.SQUAD:
                scope_id = squad.id
            elif scope_type == ScopeType.COMPANY:
                scope_id = squad.company_id
            elif scope_type == ScopeType.CONTINGENT:
                scope_id = squad.contingent_id
            else:
                scope_id = squad.unit_id

            _ensure_role_assignment(
                db,
                user=user,
                role=role,
                scope_type=scope_type,
                scope_id=scope_id,
                assigned_by_id=ano_user.id,
            )

            cadet_no = f"NCC-2026-{cadet_counter:04d}"
            division = "SD" if cadet_counter % 2 == 1 else "SW"
            _ensure_cadet_profile(
                db,
                user=user,
                squad=squad,
                cadet_no=cadet_no,
                rank=rank,
                division=division,
                changed_by_id=ano_user.id,
            )

    db.commit()

    return {
        "units": db.query(Unit).count(),
        "contingents": db.query(Contingent).count(),
        "companies": db.query(Company).count(),
        "squads": db.query(Squad).count(),
        "users": db.query(User).count(),
        "cadets": db.query(CadetProfile).count(),
    }


def main() -> None:
    """CLI entrypoint for python -m database.seed."""
    get_engine()
    with SessionLocal() as db:
        counts = seed_database(db)
    print(
        "CADENCE seed complete:",
        ", ".join(f"{k}={v}" for k, v in counts.items()),
    )


if __name__ == "__main__":
    main()
