from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from urllib.parse import urlparse

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./innovo.db")

parsed_url = urlparse(DATABASE_URL)
is_sqlite = parsed_url.scheme == "sqlite" or "sqlite" in DATABASE_URL.lower()
is_postgres = parsed_url.scheme in ("postgres", "postgresql") or parsed_url.scheme.startswith("postgresql")

if is_sqlite:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
elif is_postgres:
    connect_args = {}
    if "sslmode" not in DATABASE_URL.lower():
        connect_args["sslmode"] = "require"
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args=connect_args,
    )
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
