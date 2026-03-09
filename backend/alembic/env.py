# Standard library imports
import os
import sys
from logging.config import fileConfig
from pathlib import Path

# Third-party imports
from sqlalchemy import engine_from_config, pool
from alembic import context

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Load .env file from backend directory
    backend_dir = Path(__file__).resolve().parent.parent
    env_path = backend_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    # python-dotenv not installed, skip
    pass

# Add the backend directory to the path so we can import app modules
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

# Application imports
# Note: These imports are after path setup to ensure app modules can be imported
from app.database import Base  # noqa: E402
# Import all models so Alembic can detect them for autogenerate
# Note: These imports appear unused but are required for Alembic autogenerate
from app.models import (  # noqa: F401, E402
    User, FundingProgram, Company, Document, funding_program_companies,
    File, AudioTranscriptCache, WebsiteTextCache, DocumentTextCache,
    FundingProgramDocument, UserTemplate, FundingProgramGuidelinesSummary,
    CompanyDocument, AlteVorhabensbeschreibungDocument, AlteVorhabensbeschreibungStyleProfile
)

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url():
    """
    Get database URL from environment variable.
    Production (Render): DATABASE_URL must be set to PostgreSQL connection string
    Local development: Falls back to SQLite if DATABASE_URL is not set
    """
    # Read DATABASE_URL from environment (same as app/database.py)
    database_url = os.getenv("DATABASE_URL", "sqlite:///./innovo.db")
    return database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Get database URL from environment
    database_url = get_url()

    # Configure Alembic with the database URL
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = database_url

    # Set up connect_args based on database type
    connect_args = {}
    if "sqlite" in database_url:
        # SQLite configuration
        connect_args["check_same_thread"] = False
    elif database_url.startswith("postgres"):
        # PostgreSQL configuration for production (Render)
        # Production requires DATABASE_URL to be set to a PostgreSQL connection string
        # Add SSL mode if not already in URL (required for Render Postgres)
        if "sslmode" not in database_url.lower():
            connect_args["sslmode"] = "require"

    # Create engine with appropriate settings
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

