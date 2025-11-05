from typing import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool

from app.config import settings
from app.exceptions import DatabaseError
from app.logging_config import logger

Base = declarative_base()


def get_engine() -> Engine:
    """
    Create and return SQLAlchemy engine

    returns:
        SQLAlchemy engine instance
    """
    try:
        engine = create_engine(
            settings.database_url,
            echo=settings.sqlalchemy_echo,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
        logger.info("Database engine created successfully")
        return engine
    except Exception as e:
        logger.error(f"Failed to create database engine: {e}")
        raise DatabaseError(f"Failed to create database engine: {e}")


# Create engine
engine = get_engine()

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection function for FastAPI to get database session.

    Yields:
        Database session

    Raises:
        DatabaseError: If session creation fails
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise DatabaseError(f"Database session error: {e}")
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database by creating all tables.

    Raises:
        DatabaseError: If initialization fails
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise DatabaseError(f"Failed to initialize database: {e}")


def drop_all_tables() -> None:
    """
    Drop all tables from the database (for testing).

    Raises:
        DatabaseError: If drop operation fails
    """
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("All database tables dropped successfully")
    except Exception as e:
        logger.error(f"Failed to drop database tables: {e}")
        raise DatabaseError(f"Failed to drop tables: {str(e)}")


__all__ = [
    "get_engine",
    "engine",
    "SessionLocal",
    "get_db",
    "init_db",
    "drop_all_tables",
]
