from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin, AuthResponse, TokenResponse, PasswordResetRequest, PasswordReset
from app.utils import hash_password, verify_password
from app.jwt_utils import create_access_token, create_password_reset_token, verify_password_reset_token
from datetime import datetime, timedelta
import logging
import hashlib

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):  # noqa: B008
    """
    Create a new user account.

    Security: Passwords are hashed with bcrypt before storage.
    Email validation ensures only allowed domains can register.
    """
    # Normalize email to lowercase for consistent storage
    email_lower = user_data.email.lower()

    # Check if user already exists (case-insensitive query using func.lower)
    # This ensures we catch duplicates regardless of how they were stored
    existing_user = db.query(User).filter(func.lower(User.email) == email_lower).first()

    if existing_user:
        logger.info(f"Registration attempt with existing email: {email_lower}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already exists. Please log in."
        )

    # Hash password - NEVER store plain text passwords
    # bcrypt automatically handles salting and hashing
    password_hash = hash_password(user_data.password)

    # Create new user
    new_user = User(
        email=email_lower,
        password_hash=password_hash
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info(f"New user registered: {new_user.email}")
        try:
            from posthog import new_context, identify_context, capture
            with new_context():
                identify_context(new_user.email)
                capture("user_signed_up", properties={"signup_method": "email"})
        except Exception as e:
            logger.debug("PostHog identify/capture skipped: %s", e)
        return AuthResponse(
            success=True,
            message="Account created successfully"
        )
    except IntegrityError:
        # Handle database-level unique constraint violation
        # This catches duplicates even if the query above missed them (race condition, etc.)
        db.rollback()
        logger.warning(f"Registration attempt with duplicate email (caught by DB constraint): {email_lower}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account already exists. Please log in."
        ) from None
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create account for {user_data.email}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create account"
        ) from e

@router.post("/login", response_model=TokenResponse)
def login(user_data: UserLogin, db: Session = Depends(get_db)):  # noqa: B008
    """
    Authenticate user and issue JWT access token.

    Security:
    - Verifies password using bcrypt (constant-time comparison)
    - Issues JWT token with expiration time
    - Token includes user email for authorization
    - Never returns password or password hash
    """
    # Find user by email (case-insensitive)
    user = db.query(User).filter(User.email == user_data.email.lower()).first()

    if not user:
        # Use generic message to prevent user enumeration attacks
        # Don't reveal whether email exists in system
        logger.warning(f"Login attempt with non-existent email: {user_data.email.lower()}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Verify password - bcrypt handles constant-time comparison
    # This prevents timing attacks that could reveal if email exists
    if not verify_password(user_data.password, user.password_hash):
        logger.warning(f"Failed login attempt for: {user_data.email.lower()}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Create JWT access token
    # Token includes email for user identification
    # Expiration is set in jwt_utils.py (24 hours by default)
    access_token = create_access_token(data={"email": user.email})

    logger.info(f"User logged in successfully: {user.email}")
    try:
        from posthog import new_context, identify_context, capture
        with new_context():
            identify_context(user.email)
            capture("user_logged_in")
    except Exception as e:
        logger.debug("PostHog identify/capture skipped: %s", e)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",  # noqa: B106 - Standard OAuth 2.0 token type, not a password
        success=True,
        message="Login successful"
    )


@router.post("/request-password-reset", response_model=AuthResponse)
def request_password_reset(
    reset_request: PasswordResetRequest,
    db: Session = Depends(get_db)  # noqa: B008
):
    """
    Request a password reset token.

    Security:
    - Generates time-limited reset token (1 hour expiration)
    - Stores hashed token in database
    - Returns token for development (in production, send via email)
    - Prevents user enumeration by always returning success

    Note: In production, the token should be sent via email.
    For development, the token is returned in the response.
    """
    # Find user by email
    user = db.query(User).filter(User.email == reset_request.email.lower()).first()

    # Always return success to prevent user enumeration
    # Don't reveal whether email exists in system
    if not user:
        logger.info(f"Password reset requested for non-existent email: {reset_request.email.lower()}")
        # Return success even if user doesn't exist (security best practice)
        return AuthResponse(
            success=True,
            message="If the email exists, a password reset token has been generated."
        )

    # Generate password reset token
    reset_token = create_password_reset_token(user.email)

    # Hash the token before storing (security: if DB is compromised, tokens can't be used)
    # Use SHA256 for deterministic hashing (bcrypt produces different hashes each time)
    reset_token_hash = hashlib.sha256(reset_token.encode()).hexdigest()

    # Set token expiration (1 hour from now)
    reset_token_expiry = datetime.utcnow() + timedelta(hours=1)

    # Store reset token in database
    user.reset_token_hash = reset_token_hash
    user.reset_token_expiry = reset_token_expiry

    try:
        db.commit()
        logger.info(f"Password reset token generated for: {user.email}")

        # DEVELOPMENT ONLY: Return token in response
        # In production, send token via email and remove this
        return AuthResponse(
            success=True,
            message=f"Password reset token generated. Token (DEV ONLY): {reset_token}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to generate password reset token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process password reset request"
        ) from e


@router.post("/reset-password", response_model=AuthResponse)
def reset_password(
    reset_data: PasswordReset,
    db: Session = Depends(get_db)  # noqa: B008
):
    """
    Reset password using a valid reset token.

    Security:
    - Verifies token signature and expiration
    - Validates token hasn't been used (checks database)
    - Hashes new password before storage
    - Invalidates old reset token after use
    """
    # Verify reset token
    email = verify_password_reset_token(reset_data.token)
    if not email:
        logger.warning("Password reset attempted with invalid token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    # Find user
    user = db.query(User).filter(User.email == email).first()
    if not user:
        logger.warning(f"Password reset attempted for non-existent user: {email}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Verify token hasn't expired in database
    if user.reset_token_expiry is None or user.reset_token_expiry < datetime.utcnow():
        logger.warning(f"Password reset attempted with expired token for: {email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired"
        )

    # Verify token matches stored hash
    # Hash the provided token and compare with stored hash
    provided_token_hash = hashlib.sha256(reset_data.token.encode()).hexdigest()
    if user.reset_token_hash != provided_token_hash:
        logger.warning(f"Password reset attempted with mismatched token for: {email}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reset token"
        )

    # Hash new password
    new_password_hash = hash_password(reset_data.new_password)

    # Update password and invalidate reset token
    user.password_hash = new_password_hash
    user.reset_token_hash = None
    user.reset_token_expiry = None

    try:
        db.commit()
        logger.info(f"Password reset successful for: {email}")
        return AuthResponse(
            success=True,
            message="Password reset successful. Please log in with your new password."
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to reset password: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password"
        ) from e

