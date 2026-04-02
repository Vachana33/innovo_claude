"""Authentication dependencies for FastAPI routes."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from innovo_backend.shared.database import get_db
from innovo_backend.shared.jwt_utils import verify_token
import logging

logger = logging.getLogger(__name__)

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
):
    """Dependency to get the current authenticated user from JWT token."""
    from innovo_backend.shared.models import User  # avoid circular import at module level

    token = credentials.credentials

    payload = verify_token(token)
    if payload is None:
        logger.warning("Authentication failed: Invalid or expired token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email: str = payload.get("email")
    if email is None:
        logger.warning("Authentication failed: Token missing email")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required information",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        logger.warning(f"Authentication failed: User not found for email: {email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"User authenticated: {email}")
    return user


def require_admin(current_user) -> None:
    """Call at the top of any admin-only endpoint after get_current_user().

    Raises HTTP 403 with a consistent message if the user is not an admin.
    Import and call pattern (same as get_current_user):

        from innovo_backend.shared.dependencies import get_current_user, require_admin

        def my_endpoint(current_user: User = Depends(get_current_user)):
            require_admin(current_user)
            ...
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
