"""JIRA configuration manager."""

import re
from datetime import datetime

from loguru import logger
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base

from agentllm.db.token_registry import TokenTypeConfig, get_global_registry
from agentllm.tools.jira_toolkit import JiraTools

from .base import BaseToolkitConfig

# Define token model for JIRA
Base = declarative_base()


class JiraToken(Base):
    """Table for storing Jira API tokens."""

    __tablename__ = "jira_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, unique=True, index=True)
    token = Column(String, nullable=False)
    server_url = Column(String, nullable=False)
    username = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Register JIRA token type with global registry
get_global_registry().register(
    "jira",
    TokenTypeConfig(
        model=JiraToken,
        encrypted_fields=["token"],
    ),
)


class JiraConfig(BaseToolkitConfig):
    """JIRA configuration manager.

    Handles:
    - JIRA token extraction from messages
    - JIRA connection validation
    - Per-user JIRA toolkit creation and management

    Setup:
        Users provide their Jira API token through chat messages.
        The token is validated by connecting to the Jira server.
    """

    def __init__(
        self,
        jira_server: str = "https://issues.redhat.com",
        token_storage=None,
        # Tool enablement flags (defaults: all read tools enabled, write tools disabled)
        get_issue: bool = True,
        get_issues_detailed: bool = True,
        get_issues_stats: bool = True,
        get_issues_summary: bool = True,
        get_fix_versions: bool = True,
        add_comment: bool = False,
        create_issue: bool = False,
        extract_sprint_info: bool = True,
        get_sprint_metrics: bool = True,
        update_issue: bool = False,
    ):
        """Initialize JIRA configuration.

        Args:
            jira_server: JIRA server URL
            token_storage: TokenStorage instance for database-backed credentials
            get_issue: Enable get_issue tool (default: True)
            get_issues_detailed: Enable get_issues_detailed tool (default: True)
            get_issues_stats: Enable get_issues_stats tool (default: True)
            get_issues_summary: Enable get_issues_summary tool (default: True)
            get_fix_versions: Enable get_fix_versions tool (default: True)
            add_comment: Enable add_comment tool (default: False)
            create_issue: Enable create_issue tool (default: False)
            extract_sprint_info: Enable extract_sprint_info tool (default: True)
            get_sprint_metrics: Enable get_sprint_metrics tool (default: True)
            update_issue: Enable update_issue tool (default: False)
        """
        super().__init__(token_storage)
        self._jira_server = jira_server

        # Store tool configuration
        self._tool_config = {
            "get_issue": get_issue,
            "get_issues_detailed": get_issues_detailed,
            "get_issues_stats": get_issues_stats,
            "get_issues_summary": get_issues_summary,
            "get_fix_versions": get_fix_versions,
            "add_comment": add_comment,
            "create_issue": create_issue,
            "extract_sprint_info": extract_sprint_info,
            "get_sprint_metrics": get_sprint_metrics,
            "update_issue": update_issue,
        }

        # Store per-user JIRA toolkits (in-memory cache)
        self._jira_toolkits: dict[str, JiraTools] = {}

    def is_configured(self, user_id: str) -> bool:
        """Check if JIRA is configured for user.

        Args:
            user_id: User identifier

        Returns:
            True if user has a valid JIRA token
        """
        # Check database storage first (preferred)
        if self.token_storage:
            token_data = self.token_storage.get_token("jira", user_id)
            if token_data:
                return True

        # Fall back to legacy in-memory storage
        if user_id in self._user_configs and "jira_token" in self._user_configs[user_id]:
            return True

        return False

    def extract_and_store_config(self, message: str, user_id: str) -> str | None:
        """Extract and store JIRA token from user message.

        Supports patterns like:
        - "my jira token is abc123"
        - "jira token: abc123"
        - "jira_token = abc123"
        - "set jira token to abc123"
        - Standalone long alphanumeric tokens (30+ characters)

        Args:
            message: User message that may contain JIRA token
            user_id: User identifier

        Returns:
            Confirmation message if token was extracted and stored,
            None if no token found in message

        Raises:
            ValueError: If JIRA token is invalid
        """
        # Try to extract JIRA token
        token = self._extract_jira_token(message)

        if not token:
            return None

        logger.info(f"Validating Jira token for user {user_id}")

        try:
            # Create toolkit with the token using configured tool settings
            toolkit = JiraTools(
                token=token,
                server_url=self._jira_server,
                **self._tool_config,
            )

            # Validate the connection
            success, validation_message = toolkit.validate_connection()

            if not success:
                logger.error(f"Jira token validation failed for user {user_id}: {validation_message}")
                raise ValueError(f"Invalid Jira token: {validation_message}")

            logger.info(f"Jira token validated successfully for user {user_id}")

            # Store the token in database if available, otherwise in memory
            if self.token_storage:
                self.token_storage.upsert_token(
                    "jira",
                    user_id=user_id,
                    token=token,
                    server_url=self._jira_server,
                )
                logger.info(f"Stored Jira token in database for user {user_id}")
            else:
                # Fall back to in-memory storage (legacy)
                if user_id not in self._user_configs:
                    self._user_configs[user_id] = {}
                self._user_configs[user_id]["jira_token"] = token
                logger.info(f"Stored Jira token in memory for user {user_id}")

            # Store the toolkit for this user
            self._jira_toolkits[user_id] = toolkit

            # Return confirmation with validation message
            return (
                f"✅ JIRA configured successfully!\n\n{validation_message}\n\nYou can now ask me to search for issues or get issue details."
            )

        except Exception as e:
            logger.error(f"Failed to validate Jira token for user {user_id}: {e}")
            raise ValueError(f"Failed to validate Jira token: {str(e)}") from e

    def get_config_prompt(self, user_id: str) -> str | None:
        """Get prompt for JIRA token.

        Args:
            user_id: User identifier

        Returns:
            Prompt if not configured, None if configured
        """
        if self.is_configured(user_id):
            return None

        return (
            "🔑 **JIRA Configuration Required**\n\n"
            "To access JIRA, please provide your API token:\n\n"
            "Say: 'My Jira token is YOUR_TOKEN_HERE'\n\n"
            "To get a JIRA API token:\n"
            f"1. Go to {self._jira_server}\n"
            "2. Click your profile icon → Account Settings\n"
            "3. Go to Security → API Tokens\n"
            "4. Create a new token and copy it\n"
            "5. Send it to me in the format above"
        )

    def get_toolkit(self, user_id: str) -> JiraTools | None:
        """Get JIRA toolkit for user if configured.

        Args:
            user_id: User identifier

        Returns:
            JiraTools instance if configured, None otherwise
        """
        # Return cached toolkit if available
        if user_id in self._jira_toolkits:
            return self._jira_toolkits[user_id]

        # If we have token but no toolkit (e.g., after restart), recreate it
        if not self.is_configured(user_id):
            return None

        # Recreate toolkit from database or memory
        toolkit = None
        if self.token_storage:
            # Get credentials from database
            try:
                token_data = self.token_storage.get_token("jira", user_id)
                if not token_data:
                    logger.error(f"No Jira token found in database for user {user_id}")
                    return None

                toolkit = JiraTools(
                    token=token_data["token"],
                    server_url=token_data["server_url"],
                    username=token_data.get("username"),
                    **self._tool_config,
                )
                logger.info(f"Recreated JIRA toolkit from database for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to create JIRA toolkit from database: {e}")
                return None
        else:
            # Use legacy in-memory authentication
            if user_id in self._user_configs and "jira_token" in self._user_configs[user_id]:
                token = self._user_configs[user_id]["jira_token"]
                toolkit = JiraTools(
                    token=token,
                    server_url=self._jira_server,
                    **self._tool_config,
                )
                logger.info(f"Recreated JIRA toolkit (legacy) for user {user_id}")

        if toolkit:
            self._jira_toolkits[user_id] = toolkit

        return toolkit

    def check_authorization_request(self, message: str, user_id: str) -> str | None:
        """Check if message requests JIRA access and prompt if needed.

        Args:
            message: User message
            user_id: User identifier

        Returns:
            JIRA token prompt if user needs to configure, None otherwise
        """
        # Check if message mentions JIRA
        jira_keywords = [
            "jira",
            "issue",
            "ticket",
            "issues.redhat.com",
        ]

        message_lower = message.lower()
        mentions_jira = any(keyword in message_lower for keyword in jira_keywords)

        if not mentions_jira:
            return None

        # Check if user already has JIRA configured
        if self.is_configured(user_id):
            logger.info(f"User {user_id} has JIRA access")
            return None

        # User needs to configure JIRA
        return self.get_config_prompt(user_id)

    def requires_agent_recreation(self, config_name: str) -> bool:
        """Check if this config requires agent recreation.

        JIRA token configuration adds new tools to the agent.

        Args:
            config_name: Configuration name

        Returns:
            True if config is jira_token
        """
        return config_name == "jira_token"

    def get_agent_instructions(self, user_id: str) -> list[str]:
        """Get JIRA-specific agent instructions.

        Args:
            user_id: User identifier

        Returns:
            List of instruction strings
        """
        if self.get_toolkit(user_id):
            return [
                f"You have access to JIRA tools to search issues and get issue details "
                f"from {self._jira_server}. Use these tools when users ask about JIRA issues."
            ]
        return []

    # Private helper methods

    def _extract_jira_token(self, message: str) -> str | None:
        """Extract JIRA token from user message.

        Args:
            message: User message text

        Returns:
            Extracted token or None if not found
        """
        # Create flexible regex patterns
        config_name = "jira_token"
        config_pattern = config_name.replace("_", "[ _-]")

        patterns = [
            # "my jira token is VALUE"
            rf"(?:my\s+)?{config_pattern}\s+(?:is|=|:)\s+([^\s]+)",
            # "set jira token to VALUE"
            rf"set\s+{config_pattern}\s+to\s+([^\s]+)",
            # "jira token: VALUE" or "jira_token: VALUE"
            rf"{config_pattern}:\s*([^\s]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1)

        # Try to detect standalone long alphanumeric tokens (30+ characters)
        # Match standalone tokens that are likely Jira tokens:
        # - 30+ characters
        # - Contains letters and numbers
        # - May contain special chars like +, /, =
        token_pattern = r"(?:^|\s)([A-Za-z0-9+/=]{30,})(?:\s|$)"
        match = re.search(token_pattern, message)
        if match:
            potential_token = match.group(1)
            # Basic validation: should have both letters and numbers
            has_letters = bool(re.search(r"[A-Za-z]", potential_token))
            has_numbers = bool(re.search(r"[0-9]", potential_token))
            if has_letters and has_numbers:
                return potential_token

        return None
