from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from urllib.parse import urlparse

# Database URL - reads from environment variable
# Production (Supabase): DATABASE_URL must be set to Supabase PostgreSQL connection string
# Local development: Falls back to SQLite if DATABASE_URL is not set
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./innovo.db")

# Determine database type and configure engine accordingly
# Use urlparse to robustly detect database type from connection string scheme
parsed_url = urlparse(DATABASE_URL)
is_sqlite = parsed_url.scheme == "sqlite" or "sqlite" in DATABASE_URL.lower()
# PostgreSQL can use either postgres:// or postgresql:// scheme (both are valid)
# Also handle driver variants like postgresql+psycopg2://
is_postgres = parsed_url.scheme in ("postgres", "postgresql") or parsed_url.scheme.startswith("postgresql")

if is_sqlite:
    # SQLite configuration (local development only)
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
elif is_postgres:
    # PostgreSQL configuration for production (Supabase)
    # Production requires DATABASE_URL to be set to a PostgreSQL connection string
    # Handle SSL for Supabase Postgres (required for secure connections)
    connect_args = {}
    if "sslmode" not in DATABASE_URL.lower():
        connect_args["sslmode"] = "require"

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Verify connections before using (important for production)
        pool_size=5,  # Number of connections to maintain
        max_overflow=10,  # Additional connections beyond pool_size
        connect_args=connect_args
    )
else:
    # Fallback for other database types
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

