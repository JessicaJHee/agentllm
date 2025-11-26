"""OAuth state token generation and validation for CSRF protection.

This module provides utilities for generating and validating cryptographically
signed state tokens to prevent CSRF attacks in OAuth flows.
"""

import os
from datetime import UTC, datetime, timedelta

import jwt
from loguru import logger


class StateTokenError(Exception):
    """Base exception for state token errors."""

    pass


class StateTokenExpiredError(StateTokenError):
    """Raised when a state token has expired."""

    pass


class StateTokenInvalidError(StateTokenError):
    """Raised when a state token is invalid."""

    pass


# Get secret key from environment - REQUIRED for OAuth callback server
_STATE_SECRET_KEY = os.environ.get("AGENTLLM_OAUTH_STATE_SECRET")
if not _STATE_SECRET_KEY:
    raise ValueError(
        "AGENTLLM_OAUTH_STATE_SECRET environment variable is required for OAuth callback server. "
        'Generate a secure secret with: python -c "import secrets; print(secrets.token_hex(32))" '
        "and add it to your .env.secrets file. See .env.secrets.template for details."
    )

# State token expiration time (10 minutes)
_STATE_TOKEN_EXPIRY_MINUTES = 10


def generate_state_token(user_id: str) -> str:
    """Generate a cryptographically signed state token for OAuth CSRF protection.

    The state token is a JWT containing:
    - user_id: The user identifier
    - exp: Expiration time (10 minutes from now)
    - iat: Issued at time

    Args:
        user_id: User identifier to encode in the state token

    Returns:
        Signed JWT state token string

    Example:
        >>> token = generate_state_token("user123")
        >>> user_id = validate_state_token(token)
        >>> assert user_id == "user123"
    """
    now = datetime.now(UTC)
    expiry = now + timedelta(minutes=_STATE_TOKEN_EXPIRY_MINUTES)

    payload = {
        "user_id": user_id,
        "exp": expiry,
        "iat": now,
    }

    token = jwt.encode(payload, _STATE_SECRET_KEY, algorithm="HS256")
    logger.debug(f"Generated state token for user {user_id} (expires in {_STATE_TOKEN_EXPIRY_MINUTES} minutes)")

    return token


def validate_state_token(state_token: str) -> str:
    """Validate a state token and extract the user_id.

    Args:
        state_token: The signed JWT state token to validate

    Returns:
        The user_id extracted from the validated token

    Raises:
        StateTokenExpiredError: If the token has expired
        StateTokenInvalidError: If the token is invalid or malformed

    Example:
        >>> token = generate_state_token("user123")
        >>> user_id = validate_state_token(token)
        >>> assert user_id == "user123"
    """
    try:
        # Decode and validate the JWT
        payload = jwt.decode(
            state_token,
            _STATE_SECRET_KEY,
            algorithms=["HS256"],
            options={"require": ["exp", "iat", "user_id"]},
        )

        user_id = payload.get("user_id")
        if not user_id:
            raise StateTokenInvalidError("State token missing user_id")

        logger.debug(f"Successfully validated state token for user {user_id}")
        return user_id

    except jwt.ExpiredSignatureError as e:
        logger.warning(f"State token expired: {e}")
        raise StateTokenExpiredError("OAuth state token has expired. Please restart the authorization process.") from e

    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid state token: {e}")
        raise StateTokenInvalidError("Invalid OAuth state token. Possible CSRF attack detected.") from e

    except Exception as e:
        logger.error(f"Unexpected error validating state token: {e}")
        raise StateTokenInvalidError(f"Failed to validate state token: {str(e)}") from e
