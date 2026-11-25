"""Pytest configuration and shared fixtures for Cadence test suite."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base, get_db
from core.models import Role, Squad, Unit, User
from core.security import create_access_token, hash_password
from main import app

# In-memory SQLite engine for fast, isolated tests
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all tables before tests run and drop them after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a fresh, clean database session wrapped in a transaction for each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Test client overriding the get_db dependency."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seed_data(db_session: Session):
    """Seed foundational Unit, Squads, and Users for all five roles."""
    unit = Unit(name="1 PB BN NCC", code="1PBBN")
    db_session.add(unit)
    db_session.flush()

    squad1 = Squad(unit_id=unit.id, name="Alpha Squad")
    squad2 = Squad(unit_id=unit.id, name="Bravo Squad")
    db_session.add_all([squad1, squad2])
    db_session.flush()

    password_hash = hash_password("CadencePass123!")

    co = User(
        email="co@cadence.ncc",
        hashed_password=password_hash,
        full_name="Col. R. Sharma",
        cadet_number="OFFICER-001",
        rank="Colonel",
        role=Role.CO,
        unit_id=unit.id,
        is_active=True,
    )
    ano = User(
        email="ano@cadence.ncc",
        hashed_password=password_hash,
        full_name="Capt. V. Verma",
        cadet_number="OFFICER-002",
        rank="Captain",
        role=Role.ANO,
        unit_id=unit.id,
        is_active=True,
    )
    juo = User(
        email="juo@cadence.ncc",
        hashed_password=password_hash,
        full_name="JUO A. Singh",
        cadet_number="CADET-JUO-01",
        rank="JUO",
        role=Role.JUO,
        unit_id=unit.id,
        squad_id=squad1.id,
        is_active=True,
    )
    leader = User(
        email="leader@cadence.ncc",
        hashed_password=password_hash,
        full_name="Sgt. K. Patel",
        cadet_number="CADET-SGT-01",
        rank="Sergeant",
        role=Role.LEADER,
        unit_id=unit.id,
        squad_id=squad1.id,
        is_active=True,
    )
    cadet1 = User(
        email="cadet1@cadence.ncc",
        hashed_password=password_hash,
        full_name="Cdt. N. Kumar",
        cadet_number="CADET-CDT-01",
        rank="Cadet",
        role=Role.CADET,
        unit_id=unit.id,
        squad_id=squad1.id,
        is_active=True,
    )
    cadet2 = User(
        email="cadet2@cadence.ncc",
        hashed_password=password_hash,
        full_name="Cdt. P. Rao",
        cadet_number="CADET-CDT-02",
        rank="Cadet",
        role=Role.CADET,
        unit_id=unit.id,
        squad_id=squad2.id,
        is_active=True,
    )

    users = [co, ano, juo, leader, cadet1, cadet2]
    db_session.add_all(users)
    db_session.flush()

    return {
        "unit": unit,
        "squad1": squad1,
        "squad2": squad2,
        "co": co,
        "ano": ano,
        "juo": juo,
        "leader": leader,
        "cadet1": cadet1,
        "cadet2": cadet2,
    }


def auth_headers_for(user: User) -> dict[str, str]:
    """Helper to generate Authorization header for a given user."""
    token = create_access_token(
        subject=user.id,
        role=user.role.value,
        scopes={"unit_id": user.unit_id, "squad_id": user.squad_id},
    )
    return {"Authorization": f"Bearer {token}"}
