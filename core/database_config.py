"""
Database configuration utility for Django project.
Supports both SQLite (development) and PostgreSQL (production) based on environment variables.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_database_config(base_dir, env) -> dict[str, Any]:
    """
    Get database configuration based on DATABASE_URL environment variable.

    Supports:
    - SQLite: sqlite:///path/to/db.sqlite3
    - PostgreSQL: postgres://user:password@host:port/dbname

    Args:
        base_dir: Django BASE_DIR
        env: django-environ instance

    Returns:
        Database configuration dictionary
    """
    try:
        # Try to get database configuration from environment
        database_url = env("DATABASE_URL", default="sqlite:///db.sqlite3")

        if database_url.startswith("postgres"):
            # PostgreSQL configuration
            try:
                # Test if psycopg2 is available
                import psycopg2

                logger.info("Using PostgreSQL database configuration")
                return env.db()
            except ImportError:
                logger.warning(
                    "PostgreSQL requested but psycopg2 not installed. "
                    "Falling back to SQLite. Install psycopg2-binary to use PostgreSQL."
                )
                # Fallback to SQLite
                return {
                    "default": {
                        "ENGINE": "django.db.backends.sqlite3",
                        "NAME": base_dir / "db.sqlite3",
                        "OPTIONS": {
                            "timeout": 20,
                        },
                    }
                }
        else:
            # SQLite configuration (default)
            logger.info("Using SQLite database configuration")
            if database_url == "sqlite:///db.sqlite3":
                # Default SQLite path
                return {
                    "default": {
                        "ENGINE": "django.db.backends.sqlite3",
                        "NAME": base_dir / "db.sqlite3",
                        "OPTIONS": {
                            "timeout": 20,
                        },
                    }
                }
            else:
                # Use environment variable for SQLite path
                return env.db()

    except Exception as e:
        logger.error(f"Error configuring database: {e}")
        # Ultimate fallback to SQLite
        return {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": base_dir / "db.sqlite3",
                "OPTIONS": {
                    "timeout": 20,
                },
            }
        }


def get_production_database_config(env) -> dict[str, Any]:
    """
    Get production database configuration.
    Assumes PostgreSQL with connection pooling and optimizations.
    """
    try:
        database_config = env.db()

        # Add production-specific database optimizations
        if "default" in database_config:
            database_config["default"].update(
                {
                    "CONN_MAX_AGE": 60,  # Connection pooling
                    "OPTIONS": {
                        "connect_timeout": 10,
                        "options": "-c default_transaction_isolation=read_committed",
                    },
                }
            )

        return database_config

    except Exception as e:
        logger.error(f"Error configuring production database: {e}")
        raise


def validate_database_connection(database_config: dict[str, Any]) -> bool:
    """
    Validate database connection without importing Django.
    """
    try:
        default_config = database_config.get("default", {})
        engine = default_config.get("ENGINE", "")

        if "postgresql" in engine:
            # Test PostgreSQL connection
            import psycopg2

            db_config = default_config
            conn = psycopg2.connect(
                host=db_config.get("HOST", "localhost"),
                port=db_config.get("PORT", 5432),
                database=db_config.get("NAME", ""),
                user=db_config.get("USER", ""),
                password=db_config.get("PASSWORD", ""),
            )
            conn.close()
            logger.info("PostgreSQL connection validated successfully")
            return True

        elif "sqlite" in engine:
            # Test SQLite connection
            import sqlite3

            db_path = db_config.get("NAME", "")
            conn = sqlite3.connect(db_path)
            conn.close()
            logger.info("SQLite connection validated successfully")
            return True

        return False

    except Exception as e:
        logger.warning(f"Database connection validation failed: {e}")
        return False


# Database migration utilities
def create_postgresql_database(
    database_name: str,
    user: str,
    password: str,
    host: str = "localhost",
    port: int = 5432,
):
    """
    Create PostgreSQL database and user if they don't exist.
    Note: Requires PostgreSQL to be installed and running.
    """
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

        # Connect to PostgreSQL server (to postgres database)
        conn = psycopg2.connect(
            host=host,
            port=port,
            database="postgres",
            user="postgres",  # Assumes postgres superuser
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Create user if not exists
        cursor.execute(f"SELECT 1 FROM pg_user WHERE usename = '{user}'")
        if not cursor.fetchone():
            cursor.execute(f"CREATE USER {user} WITH PASSWORD '{password}'")
            logger.info(f"Created PostgreSQL user: {user}")

        # Create database if not exists
        cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{database_name}'")
        if not cursor.fetchone():
            cursor.execute(f"CREATE DATABASE {database_name} OWNER {user}")
            logger.info(f"Created PostgreSQL database: {database_name}")

        cursor.close()
        conn.close()

        return True

    except Exception as e:
        logger.error(f"Error creating PostgreSQL database: {e}")
        return False
