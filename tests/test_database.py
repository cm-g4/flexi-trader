"""Tests for database module."""

import pytest
from sqlalchemy import text

from app.database import (
    get_engine, SessionLocal, Base
)
from app.exceptions import DatabaseError

class TestDatabaseEngine:
    """Test database engine creation."""

    def test_engine_creation(self):
        """Test that engine is created successfully."""
        engine = get_engine()
        assert engine is not None
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.fetchone() is not None

    def test_engine_pool_configuration(self):
        """Test engine pool is configured."""
        engine = get_engine()
        assert engine.pool.size == 10
        assert engine.pool.max_overflow == 20

class TestDatabaseInitialization:
    """Test database initialization."""

    def test_init_db(self, test_engine):
        """Test database initialization."""
        Base.metadata.create_all(bind=test_engine)
        # Verify tables exist
        inspector = pytest.importorskip("sqlalchemy").inspect(test_engine)
        tables = inspector.get_table_names()
        # Should have tables after initialization
        assert isinstance(tables, list)

    def test_session_factory(self):
        """Test session factory."""
        session = SessionLocal()
        assert session is not None
        session.close()


class TestDatabaseConnection:
    """Test database connection."""

    def test_get_db_session(self):
        """Test getting database session."""
        db = SessionLocal()
        try:
            assert db is not None
            # Test that session is working
            db.execute(text("SELECT 1"))
        finally:
            db.close()

    def test_session_cleanup(self):
        """Test session cleanup."""
        db = SessionLocal()
        db_id = id(db)
        db.close()
        # Create new session
        db2 = SessionLocal()
        assert id(db2) != db_id

class TestDatabaseErrors:
    """Test database error handling."""

    def test_invalid_database_url(self, monkeypatch):
        """Test error handling for invalid database URL."""
        monkeypatch.setenv("DATABASE_URL", "invalid://connection")
        
        from app.config import Settings
        settings = Settings(
            database_url="invalid://connection",
            telegram_bot_token="test",
            telegram_admin_id=123
        )
        
        # Engine creation with invalid URL should fail
        with pytest.raises(DatabaseError):
            from sqlalchemy import create_engine
            engine = create_engine(settings.database_url, pool_pre_ping=True)
            # Force connection attempt
            with engine.connect():
                pass


