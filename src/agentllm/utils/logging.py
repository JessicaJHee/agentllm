"""Safe logging utilities to prevent secret/data leaks in production.

This module provides utilities to safely log content based on environment:
- Development mode (LOG_LEVEL=DEBUG): Logs full content for debugging
- Production mode (LOG_LEVEL=INFO or higher): Logs only metadata (length, type)

Usage:
    from agentllm.utils.logging import safe_log_content, is_development_mode
    from loguru import logger

    # Safe logging of message content
    logger.debug(safe_log_content(message, "User message"))

    # Check if in development mode
    if is_development_mode():
        logger.debug(f"Full data: {data}")
    else:
        logger.info(f"Data length: {len(data)}")
"""

import os
from typing import Any


def is_development_mode() -> bool:
    """Check if we're running in development mode.

    Development mode is determined by LOG_LEVEL=DEBUG environment variable.

    Returns:
        bool: True if in development mode (DEBUG level), False otherwise
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    return log_level == "DEBUG"


def safe_log_content(
    content: Any,
    label: str = "Content",
) -> str:
    """Safely format content for logging based on environment.

    In development mode (LOG_LEVEL=DEBUG):
        - Returns full content with label

    In production mode:
        - Returns only metadata (type, length) - NO actual content

    Args:
        content: The content to log (string, dict, list, etc.)
        label: Human-readable label for the content

    Returns:
        str: Formatted log message safe for current environment

    Examples:
        >>> safe_log_content("Hello World", "Message")
        # Development: "Message (full): Hello World"
        # Production: "Message (type=str, len=11)"
    """
    if content is None:
        return f"{label}: None"

    content_str = str(content)
    content_type = type(content).__name__
    content_len = len(content_str)

    if is_development_mode():
        # Development mode: Log full content
        return f"{label} (full): {content_str}"
    else:
        # Production mode: Log only metadata (NO content)
        return f"{label} (type={content_type}, len={content_len})"


def safe_log_message(message: str, label: str = "Message") -> str:
    """Safely format a message for logging (convenience wrapper for safe_log_content).

    Args:
        message: The message to log
        label: Human-readable label for the message

    Returns:
        str: Formatted log message safe for current environment
    """
    return safe_log_content(message, label)


def safe_log_dict(data: dict, label: str = "Data") -> str:
    """Safely format a dictionary for logging.

    In development mode:
        - Returns full dictionary with keys and values

    In production mode:
        - Returns only keys and value types

    Args:
        data: The dictionary to log
        label: Human-readable label for the data

    Returns:
        str: Formatted log message safe for current environment

    Examples:
        >>> safe_log_dict({"token": "abc123", "user": "john"}, "Config")
        # Development: "Config (full): {'token': 'abc123', 'user': 'john'}"
        # Production: "Config (keys): ['token', 'user']"
    """
    if data is None:
        return f"{label}: None"

    if not isinstance(data, dict):
        return safe_log_content(data, label)

    if is_development_mode():
        # Development mode: Log full dictionary
        return f"{label} (full): {data}"
    else:
        # Production mode: Log only keys
        keys = list(data.keys())
        return f"{label} (keys={len(keys)}): {keys}"


def sanitize_for_logging(value: Any) -> str:
    """Sanitize a value for safe logging (strips sensitive data in production).

    This function is useful when you need to log a value but want to ensure
    no sensitive data is leaked in production.

    Args:
        value: The value to sanitize

    Returns:
        str: Sanitized string representation

    Examples:
        >>> sanitize_for_logging("secret_token_12345")
        # Development: "secret_token_12345"
        # Production: "<redacted: type=str, len=18>"
    """
    if value is None:
        return "None"

    if is_development_mode():
        return str(value)
    else:
        return f"<redacted: type={type(value).__name__}, len={len(str(value))}>"


def log_metadata_only(content: Any, label: str = "Content") -> str:
    """Log only metadata about content (type, length) without actual content.

    This is useful for always logging metadata regardless of environment,
    when the content itself should never be logged.

    Args:
        content: The content to describe
        label: Human-readable label

    Returns:
        str: Metadata description

    Examples:
        >>> log_metadata_only("Hello World", "Message")
        "Message (type=str, len=11)"
    """
    if content is None:
        return f"{label}: None"

    content_type = type(content).__name__
    content_len = len(str(content))

    return f"{label} (type={content_type}, len={content_len})"
