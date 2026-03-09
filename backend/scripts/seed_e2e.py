"""
Seed E2E database state for Playwright tests.

- Creates E2E login user (E2E_TEST_EMAIL, E2E_TEST_PASSWORD).
- Creates at least one FundingProgram for that user so the document creation
  dropdown has an option (e.g. selectOption({ index: 1 })).

Idempotent and safe to run multiple times. Single commit at the end.
Uses existing SQLAlchemy models and session from backend/app.

Run from backend directory:
  python scripts/seed_e2e.py
Or from repo root:
  PYTHONPATH=backend python backend/scripts/seed_e2e.py
"""
import os
import sys
from pathlib import Path

# Ensure backend/app is importable when run as script
_backend = Path(__file__).resolve().parent.parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from app.database import SessionLocal
from app.models import User, FundingProgram
from app.utils import hash_password

# Deterministic title for idempotent funding program lookup
E2E_FUNDING_PROGRAM_TITLE = "E2E Funding Program"


def _require_models() -> None:
    """Raise a clear error if required model attributes are missing."""
    missing = []
    if not hasattr(User, "email"):
        missing.append("User.email")
    if not hasattr(User, "password_hash"):
        missing.append("User.password_hash")
    if not hasattr(FundingProgram, "title"):
        missing.append("FundingProgram.title")
    if not hasattr(FundingProgram, "user_email"):
        missing.append("FundingProgram.user_email")
    if missing:
        raise RuntimeError(
            f"Required model attributes missing: {', '.join(missing)}. "
            "Ensure backend models define these columns."
        )


def main() -> None:
    email = os.environ.get("E2E_TEST_EMAIL")
    password = os.environ.get("E2E_TEST_PASSWORD")

    if not email or not email.strip():
        raise SystemExit(
            "Error: E2E_TEST_EMAIL is required. Set it in the environment (e.g. .env.e2e)."
        )
    if not password or not password.strip():
        raise SystemExit(
            "Error: E2E_TEST_PASSWORD is required. Set it in the environment (e.g. .env.e2e)."
        )

    email = email.strip()
    password = password.strip()

    _require_models()

    db = SessionLocal()
    try:
        user_created = False
        program_created = False

        # --- E2E user (idempotent) ---
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print("E2E user exists")
        else:
            password_hash = hash_password(password)
            user = User(email=email, password_hash=password_hash)
            db.add(user)
            user_created = True
            print("Created E2E user")

        # --- At least one funding program for this user (idempotent) ---
        existing_program = (
            db.query(FundingProgram)
            .filter(FundingProgram.user_email == email)
            .first()
        )
        if existing_program:
            print("Funding program already exists")
        else:
            program = FundingProgram(
                title=E2E_FUNDING_PROGRAM_TITLE,
                website=None,
                user_email=email,
            )
            db.add(program)
            program_created = True
            print("Created funding program")

        if user_created or program_created:
            db.commit()
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
