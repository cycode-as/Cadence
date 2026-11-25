"""Environment-based database configuration for CADENCE."""

from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str | None, default: int) -> int:
    if value is None or not value.strip():
        return default
    return int(value)


def normalize_database_url(url: str) -> str:
    """Normalize PostgreSQL URL schemes for the installed DBAPI driver.

    - Converts legacy ``postgres://`` scheme to ``postgresql://``.
    - If no explicit driver (``+...``) is specified and ``psycopg`` (v3) is
      installed without ``psycopg2``, rewrites ``postgresql://`` to
      ``postgresql+psycopg://`` so SQLAlchemy loads the installed driver.
    """
    normalized = url.strip()
    if normalized.startswith("postgres://"):
        normalized = "postgresql://" + normalized[len("postgres://") :]

    if normalized.startswith("postgresql://"):
        has_psycopg2 = importlib.util.find_spec("psycopg2") is not None
        has_psycopg3 = importlib.util.find_spec("psycopg") is not None
        if not has_psycopg2 and has_psycopg3:
            normalized = "postgresql+psycopg://" + normalized[len("postgresql://") :]

    return normalized


@dataclass(frozen=True)
class DatabaseSettings:
    """Database configuration loaded strictly from environment variables."""

    database_url: str | None
    echo: bool = False
    pool_pre_ping: bool = True
    pool_size: int = 5
    max_overflow: int = 10

    @classmethod
    def from_env(cls) -> DatabaseSettings:
        """Load current database settings from environment variables."""
        load_dotenv()
        raw_url = os.getenv("DATABASE_URL")
        normalized_url = normalize_database_url(raw_url) if raw_url and raw_url.strip() else None
        return cls(
            database_url=normalized_url,
            echo=_parse_bool(os.getenv("DB_ECHO"), default=False),
            pool_pre_ping=_parse_bool(os.getenv("DB_POOL_PRE_PING"), default=True),
            pool_size=_parse_int(os.getenv("DB_POOL_SIZE"), default=5),
            max_overflow=_parse_int(os.getenv("DB_MAX_OVERFLOW"), default=10),
        )


def get_database_url() -> str | None:
    """Return the normalized DATABASE_URL from the environment, or None if unset."""
    return DatabaseSettings.from_env().database_url


def require_database_url() -> str:
    """Return DATABASE_URL from the environment or raise a clear RuntimeError."""
    url = get_database_url()
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Configure DATABASE_URL in your environment or .env file."
        )
    return url


settings = DatabaseSettings.from_env()

__all__ = [
    "DatabaseSettings",
    "get_database_url",
    "normalize_database_url",
    "require_database_url",
    "settings",
]
