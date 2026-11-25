"""SQLAlchemy engine, SessionLocal, and synchronous get_db() dependency."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from database.base import Base
from database.config import DatabaseSettings, normalize_database_url, require_database_url


def create_db_engine(database_url: str | None = None) -> Engine:
    """Create a synchronous SQLAlchemy Engine from DATABASE_URL."""
    current_settings = DatabaseSettings.from_env()
    resolved_url = (
        normalize_database_url(database_url)
        if database_url is not None
        else (current_settings.database_url or require_database_url())
    )

    engine_kwargs: dict[str, object] = {
        "echo": current_settings.echo,
        "pool_pre_ping": current_settings.pool_pre_ping,
    }
    if not resolved_url.startswith("sqlite"):
        engine_kwargs["pool_size"] = current_settings.pool_size
        engine_kwargs["max_overflow"] = current_settings.max_overflow

    return create_engine(resolved_url, **engine_kwargs)


_initial_settings = DatabaseSettings.from_env()
engine: Engine | None = (
    create_db_engine(_initial_settings.database_url)
    if _initial_settings.database_url
    else None
)

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def init_engine(database_url: str | None = None) -> Engine:
    """Initialize or rebind the module engine and SessionLocal factory."""
    global engine
    engine = create_db_engine(database_url)
    SessionLocal.configure(bind=engine)
    return engine


def get_engine() -> Engine:
    """Return the active SQLAlchemy Engine, initializing from env if needed."""
    if engine is None:
        return init_engine()
    return engine


def get_db() -> Generator[Session, None, None]:
    """Yield a synchronous SQLAlchemy Session and ensure it is closed afterward."""
    get_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


__all__ = [
    "Base",
    "SessionLocal",
    "create_db_engine",
    "engine",
    "get_db",
    "get_engine",
    "init_engine",
]
