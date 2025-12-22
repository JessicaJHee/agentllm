#!/usr/bin/env python3
"""Setup ephemeral database from individual environment variables.

This script creates a fresh TokenStorage database from individual secrets,
designed for CI/CD environments like GitHub Actions where:
1. Tokens are stored as individual GitHub Secrets
2. Database is ephemeral (created fresh on each run)
3. Encryption key from GitHub Secrets (database only exists during workflow run)

Usage:
    python scripts/setup_database_from_secrets.py

Required Environment Variables:
    JIRA_API_TOKEN - Jira API token (bot service account)

Constants (hardcoded):
    JIRA_SERVER_URL - https://issues.redhat.com
    AUTOMATION_USER_ID - jira-triager-bot
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger

from agentllm.db.token_storage import TokenStorage

# Import toolkit configs to register token types with global registry
from agentllm.agents.toolkit_configs.jira_config import JiraConfig  # noqa: F401

# Constants
JIRA_SERVER_URL = "https://issues.redhat.com"
AUTOMATION_USER_ID = "jira-triager-bot"
DB_PATH = "tmp/agent-data/agno_sessions.db"


def validate_required_env_vars() -> dict[str, str]:
    """Validate and return required environment variables.

    Returns:
        Dictionary of environment variables

    Raises:
        SystemExit: If required variables are missing
    """
    required_vars = {
        "JIRA_API_TOKEN": "Jira API token (bot service account)",
    }

    env_vars = {}
    missing = []

    # Check required variables
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value:
            missing.append(f"  {var}: {description}")
        else:
            env_vars[var] = value
            logger.info(f"✓ {var} found")

    if missing:
        logger.error("Missing required environment variables:")
        for msg in missing:
            logger.error(msg)
        sys.exit(1)

    return env_vars


def setup_database(env_vars: dict[str, str]) -> TokenStorage:
    """Create and populate database from environment variables.

    Args:
        env_vars: Dictionary of environment variables

    Returns:
        Configured TokenStorage instance
    """
    from cryptography.fernet import Fernet

    db_path = Path(DB_PATH)
    user_id = AUTOMATION_USER_ID

    # Remove existing database for fresh start
    if db_path.exists():
        logger.info(f"Removing existing database: {db_path}")
        db_path.unlink()

    # Create parent directory
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate throwaway encryption key (database is ephemeral)
    encryption_key = Fernet.generate_key().decode()
    logger.debug("Generated ephemeral encryption key")

    # Save encryption key for auto_triage.py to use
    key_file = db_path.parent / ".encryption_key"
    key_file.write_text(encryption_key)
    logger.debug(f"Saved encryption key to {key_file}")

    # Create TokenStorage with generated encryption key
    logger.info(f"Creating database: {db_path}")
    token_storage = TokenStorage(
        db_file=str(db_path),
        encryption_key=encryption_key,
    )

    # Store Jira token
    logger.info(f"Storing Jira token for user {user_id}")
    success = token_storage.upsert_token(
        "jira",
        user_id,
        token=env_vars["JIRA_API_TOKEN"],
        server_url=JIRA_SERVER_URL,
        username=user_id,  # Use automation user ID as username
    )
    if not success:
        logger.error("Failed to store Jira token")
        sys.exit(1)

    # Verify token was stored
    jira_token = token_storage.get_token("jira", user_id)

    if not jira_token:
        logger.error("Failed to verify stored token")
        sys.exit(1)

    logger.info("✓ Jira token stored and verified successfully")
    return token_storage


def main():
    """Main entry point."""
    logger.info("=== Ephemeral Database Setup for CI/CD ===")
    logger.info("This script creates a fresh database from individual secrets")
    logger.info("")

    # Validate environment variables
    logger.info("Step 1: Validating environment variables")
    env_vars = validate_required_env_vars()
    logger.info("")

    # Setup database
    logger.info("Step 2: Creating and populating database")
    token_storage = setup_database(env_vars)
    logger.info("")

    # Summary
    logger.info("=== Setup Complete ===")
    logger.info(f"Database: {DB_PATH}")
    logger.info(f"Encryption key: {DB_PATH.rsplit('/', 1)[0]}/.encryption_key (auto-generated)")
    logger.info(f"User ID: {AUTOMATION_USER_ID}")
    logger.info(f"Jira Server: {JIRA_SERVER_URL}")
    logger.info("Tokens stored: Jira")
    logger.info("")
    logger.info("Ready for automation!")


if __name__ == "__main__":
    main()
