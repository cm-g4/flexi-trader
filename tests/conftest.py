"""Pytest configuration and fixtures."""

import os

# Set PYTEST_RUNNING before any imports that might use settings
# This ensures .env.test is loaded instead of .env
os.environ["PYTEST_RUNNING"] = "true"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models import Channel, Message  # Import models to register them with Base


@pytest.fixture(scope="function")
def test_db() -> Session:
    """
    Create a test database session using an in-memory SQLite database.
    
    Yields:
        SQLAlchemy session for testing
    """
    # Create in-memory SQLite database
    engine = create_engine("sqlite:///:memory:", echo=False)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        expire_on_commit=False,
    )
    
    session = TestingSessionLocal()
    
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

