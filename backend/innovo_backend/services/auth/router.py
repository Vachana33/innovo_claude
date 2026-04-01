from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from innovo_backend.shared.database import get_db
from innovo_backend.shared.models import User
from innovo_backend.shared.schemas import UserCreate, UserLogin, AuthResponse, TokenResponse, PasswordResetRequest, PasswordReset
from innovo_backend.shared.utils import hash_password, verify_password
from innovo_backend.shared.jwt_utils import create_access_token, create_password_reset_token, verify_password_reset_token
from innovo_backend.shared.dependencies import get_current_user
from datetime import datetime, timedelta
import logging
import hashlib

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):  # noqa: B008
    return {"email": current_user.email, "is_admin": current_user.is_admin}


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):  # noqa: B008
    email_lower = user_data.email.lower()
    existing_user = db.query(User).filter(func.lower(User.email) == email_lower).first()

    if existing_user:
        logger.info(f"Registration attempt with existing email: {email_lower}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Account already exists. Please log in.")

    password_hash = hash_password(user_data.password)
    new_user = User(email=email_lower, password_hash=password_hash)

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info(f"New user registered: {new_user.email}")
        return AuthResponse(success=True, message="Account created successfully")
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Account already exists. Please log in."
        ) from None
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create account"
        ) from e


@router.post("/login", response_model=TokenResponse)
def login(user_data: UserLogin, db: Session = Depends(get_db)):  # noqa: B008
    user = db.query(User).filter(User.email == user_data.email.lower()).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if not verify_password(user_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    access_token = create_access_token(data={"email": user.email})
    logger.info(f"User logged in successfully: {user.email}")

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",  # noqa: B106
        success=True,
        message="Login successful",
    )


@router.post("/request-password-reset", response_model=AuthResponse)
def request_password_reset(reset_request: PasswordResetRequest, db: Session = Depends(get_db)):  # noqa: B008
    user = db.query(User).filter(User.email == reset_request.email.lower()).first()

    if not user:
        return AuthResponse(success=True, message="If the email exists, a password reset token has been generated.")

    reset_token = create_password_reset_token(user.email)
    reset_token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
    reset_token_expiry = datetime.utcnow() + timedelta(hours=1)

    user.reset_token_hash = reset_token_hash
    user.reset_token_expiry = reset_token_expiry

    try:
        db.commit()
        return AuthResponse(
            success=True,
            message=f"Password reset token generated. Token (DEV ONLY): {reset_token}",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process password reset request"
        ) from e


@router.post("/reset-password", response_model=AuthResponse)
def reset_password(reset_data: PasswordReset, db: Session = Depends(get_db)):  # noqa: B008
    email = verify_password_reset_token(reset_data.token)
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.reset_token_expiry is None or user.reset_token_expiry < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset token has expired")

    provided_token_hash = hashlib.sha256(reset_data.token.encode()).hexdigest()
    if user.reset_token_hash != provided_token_hash:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token")

    user.password_hash = hash_password(reset_data.new_password)
    user.reset_token_hash = None
    user.reset_token_expiry = None

    try:
        db.commit()
        return AuthResponse(success=True, message="Password reset successful. Please log in with your new password.")
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to reset password"
        ) from e
