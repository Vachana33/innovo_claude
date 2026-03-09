"""
JWT token utilities for authentication.

Security considerations:
- Tokens are signed with a secret key stored in environment variables
- Tokens include expiration time (exp claim) to prevent indefinite use
- User email and identifier are included in token payload for authorization
- Tokens are validated on every protected request
"""
import os
from datetime import datetime, timedelta
from typing import Optional, Dict
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
import logging

logger = logging.getLogger(__name__)

# Get secret key from environment - CRITICAL: Must be set in production
# This secret is used to sign and verify JWT tokens
# The key should be generated using: openssl rand -hex 32
# And stored in backend/.env file as JWT_SECRET_KEY
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError(
        "JWT_SECRET_KEY environment variable is required. "
        "Generate one using: openssl rand -hex 32"
    )
ALGORITHM = "HS256"  # HMAC-SHA256 algorithm for signing

# Token expiration time - 24 hours for access tokens
# This balances security (shorter = more secure) with user convenience
ACCESS_TOKEN_EXPIRE_HOURS = 24


def create_access_token(data: Dict[str, str]) -> str:
    """
    Create a JWT access token with user information.

    Args:
        data: Dictionary containing user information (email, user_id, etc.)

    Returns:
        Encoded JWT token string

    Security: Token includes expiration time and is signed with secret key
    """
    # Create a copy to avoid mutating the original dict
    to_encode = data.copy()

    # Set expiration time - tokens expire after ACCESS_TOKEN_EXPIRE_HOURS
    # This ensures tokens cannot be used indefinitely if compromised
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})

    # Encode token with secret key and algorithm
    # The secret key ensures only our server can create valid tokens
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    logger.info(f"Access token created for user: {data.get('email', 'unknown')}")
    return encoded_jwt


def verify_token(token: str) -> Optional[Dict[str, str]]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string to verify

    Returns:
        Decoded token payload if valid, None if invalid or expired

    Security: Validates signature and expiration time
    """
    try:
        # Decode and verify token
        # This will raise an exception if:
        # - Token signature is invalid (tampered with)
        # - Token has expired
        # - Token format is incorrect
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except ExpiredSignatureError:
        # Token has expired - user must re-authenticate
        logger.warning("Attempted to use expired token")
        return None
    except InvalidTokenError as e:
        # Token is invalid (wrong signature, malformed, etc.)
        logger.warning(f"Invalid token provided: {str(e)}")
        return None
    except Exception as e:
        # Unexpected error during token verification
        logger.error(f"Error verifying token: {str(e)}")
        return None


def create_password_reset_token(email: str) -> str:
    """
    Create a time-limited token for password reset.

    Args:
        email: User email address

    Returns:
        Encoded JWT token for password reset

    Security: Reset tokens expire after 1 hour for security
    """
    # Reset tokens have shorter expiration (1 hour) for security
    # This limits the window of opportunity if token is compromised
    expire = datetime.utcnow() + timedelta(hours=1)

    to_encode = {
        "email": email,
        "type": "password_reset",  # Token type to distinguish from access tokens
        "exp": expire
    }

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    logger.info(f"Password reset token created for: {email}")
    return encoded_jwt


def verify_password_reset_token(token: str) -> Optional[str]:
    """
    Verify a password reset token and return the email.

    Args:
        token: Password reset token

    Returns:
        User email if token is valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        # Verify this is a password reset token (not an access token)
        if payload.get("type") != "password_reset":
            logger.warning("Token provided is not a password reset token")
            return None

        email = payload.get("email")
        if not email:
            logger.warning("Password reset token missing email")
            return None

        return email
    except ExpiredSignatureError:
        logger.warning("Password reset token has expired")
        return None
    except InvalidTokenError as e:
        logger.warning(f"Invalid password reset token: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error verifying password reset token: {str(e)}")
        return None

