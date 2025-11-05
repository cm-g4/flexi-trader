"""Pytest configuration and fixtures for testing."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.config import Settings
from app.logging_config import setup_logging


@pytest.fixture(scope="session")
def test_settings():
    """Provide test settings."""
    settings = Settings(
        app_env="testing",
        app_debug=True,
        database_url="sqlite:///:memory:",
        telegram_bot_token="TEST_TOKEN",
        telegram_admin_id="1234567890",
    )
    return settings


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Provide test database session."""
    connection = test_engine.connect()
    transaction = connection.begin()
    
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="session")
def test_logger():
    """Setup test logger."""
    return setup_logging(level="DEBUG")

