"""Core database compatibility module forwarding to database.session."""

from database.session import Base, SessionLocal, engine, get_db

__all__ = ["Base", "SessionLocal", "engine", "get_db"]
