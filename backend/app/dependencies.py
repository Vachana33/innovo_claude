"""
Authentication dependencies for FastAPI routes.

This module provides dependencies that can be used to protect routes
and get the current authenticated user.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.jwt_utils import verify_token
import logging

logger = logging.getLogger(__name__)

# HTTPBearer scheme for extracting token from Authorization header
# Format: Authorization: Bearer <token>
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
    db: Session = Depends(get_db)  # noqa: B008
) -> User:
    """
    Dependency to get the current authenticated user from JWT token.

    This dependency:
    1. Extracts JWT token from Authorization header
    2. Verifies token signature and expiration
    3. Retrieves user from database
    4. Returns user object for use in route handlers

    Security: Returns 401 Unauthorized if:
    - Token is missing
    - Token is invalid or expired
    - User doesn't exist in database

    Usage:
        @router.get("/protected")
        def protected_route(current_user: User = Depends(get_current_user)):
            return {"user": current_user.email}
    """
    token = credentials.credentials

    # Verify token and extract payload
    payload = verify_token(token)
    if payload is None:
        # Token is invalid or expired
        logger.warning("Authentication failed: Invalid or expired token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract email from token payload
    email: str = payload.get("email")
    if email is None:
        logger.warning("Authentication failed: Token missing email")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required information",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Retrieve user from database
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        # User doesn't exist (account may have been deleted)
        logger.warning(f"Authentication failed: User not found for email: {email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"User authenticated: {email}")
    return user










