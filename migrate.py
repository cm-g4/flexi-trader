"""Standalone script to run database migrations without CLI."""

import sys
import os
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from alembic.config import Config
from alembic import command

from app.config import settings
from app.database import init_db
from app.logging_config import logger


logger.info("Setting up Alembic configuration...")

def setup_alembic_config():
    """Setup Alembic configuration."""
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return alembic_cfg


def check_migrations_initialized():
    """Check if alembic is initialized."""
    alembic_ini = Path("alembic.ini")
    alembic_dir = Path("alembic")
    
    if not alembic_ini.exists():
        logger.error("❌ alembic.ini not found. Run: alembic init alembic")
        return False
    
    if not alembic_dir.exists():
        logger.error("❌ alembic/ directory not found")
        return False
    
    return True


def get_current_revision(alembic_cfg):
    """Get current database revision."""
    try:
        from sqlalchemy import text
        from app.database import engine
        
        with engine.connect() as conn:
            # Check if alembic_version table exists
            result = conn.execute(
                text(
                    "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
                    "WHERE table_name='alembic_version')"
                )
            )
            
            if not result.scalar():
                logger.info("ℹ️  alembic_version table doesn't exist - database is fresh")
                return None
            
            result = conn.execute(text("SELECT version_num FROM alembic_version"))
            row = result.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.warning(f"Could not determine current revision: {e}")
        return None

def get_head_revision(alembic_cfg):
    """Get head (latest) revision."""
    try:
        from alembic.script import ScriptDirectory
        script = ScriptDirectory.from_config(alembic_cfg)
        return script.get_current_head()
    except Exception as e:
        logger.error(f"Could not determine head revision: {e}")
        return None


def run_migrations():
    """Run database migrations."""
    print("\n" + "="*60)
    print("🗄️  FlexiTrader Database Migration")
    print("="*60 + "\n")
    
    # Check if Alembic is set up
    if not check_migrations_initialized():
        print("\n⚠️  Alembic is not initialized.")
        print("Please copy the alembic/ directory and alembic.ini to your project root.")
        return False
    
    try:
        # Setup Alembic
        logger.info("Setting up Alembic configuration...")
        alembic_cfg = setup_alembic_config()
        
        # Get current and head revisions
        current = get_current_revision(alembic_cfg)
        head = get_head_revision(alembic_cfg)
        
        logger.info(f"Database URL: {settings.database_url}")
        logger.info(f"Current revision: {current or 'None (fresh database)'}")
        logger.info(f"Head revision: {head}")
        
        if current == head:
            logger.info("✅ Database is already at the latest revision!")
            return True
        
        # Run migrations
        logger.info("\n🔄 Running migrations...")
        command.upgrade(alembic_cfg, "head")
        
        logger.info("✅ Migration completed successfully!")
        
        # Verify
        new_current = get_current_revision(alembic_cfg)
        logger.info(f"New revision: {new_current}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        return False

def show_migration_status():
    """Show migration status without running."""
    print("\n" + "="*60)
    print("🗄️  FlexiTrader Database Migration Status")
    print("="*60 + "\n")
    
    try:
        if not check_migrations_initialized():
            print("⚠️  Alembic is not initialized.")
            return
        
        alembic_cfg = setup_alembic_config()
        current = get_current_revision(alembic_cfg)
        head = get_head_revision(alembic_cfg)
        
        logger.info(f"Database URL: {settings.database_url}")
        logger.info(f"Current revision: {current or 'None (fresh database)'}")
        logger.info(f"Head revision: {head}")
        
        if current == head:
            logger.info("✅ Database is up to date!")
        else:
            logger.warning(f"⚠️  Database is {(head[:7] if head else 'unknown')} behind head")
            logger.info("Run: python migrate.py --run")
            
    except Exception as e:
        logger.error(f"Error checking migration status: {e}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Database migration tool for FlexiTrader"
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run migrations"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show migration status (default)"
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Initialize database tables"
    )
    
    args = parser.parse_args()
    
    try:
        if args.init:
            logger.info("Initializing database tables...")
            init_db()
            logger.info("✅ Database tables initialized")
        
        if args.run or (not args.status and not args.init):
            success = run_migrations()
            return 0 if success else 1
        else:
            show_migration_status()
            return 0
            
    except KeyboardInterrupt:
        logger.info("\n⚠️  Migration cancelled by user")
        return 1
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())