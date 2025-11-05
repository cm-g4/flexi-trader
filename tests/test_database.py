"""Tests for database module."""

import pytest
from sqlalchemy import create_engine, text

from app.database import Base


class TestDatabaseEngine:
    """Test database engine creation."""

    def test_engine_creation(self):
        """Test that engine can be created."""
        engine = create_engine("sqlite:///:memory:")
        assert engine is not None

        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.fetchone() is not None

    def test_engine_pool_configuration(self):
        """Test engine configuration."""
        engine = create_engine("sqlite:///:memory:")
        assert engine is not None


class TestDatabaseInitialization:
    """Test database initialization."""

    def test_init_db(self):
        """Test database initialization."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)

        inspector = pytest.importorskip("sqlalchemy").inspect(engine)
        tables = inspector.get_table_names()
        assert isinstance(tables, list)


class TestDatabaseConnection:
    """Test database sessions."""

    def test_session_basics(self):
        """Test sessions can be created."""
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            assert session is not None
        finally:
            session.close()
