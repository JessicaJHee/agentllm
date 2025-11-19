"""GitHub configuration manager."""

import re

from loguru import logger

from .base import BaseToolkitConfig


class GitHubConfig(BaseToolkitConfig):
    """GitHub configuration manager.

    Handles:
    - GitHub token extraction from messages
    - GitHub connection validation
    - Per-user GitHub toolkit creation and management

    Setup:
        Users provide their GitHub personal access token through chat messages.
        The token is validated by authenticating with the GitHub API.
    """

    def __init__(self, server_url: str = "https://api.github.com", token_storage=None):
        """Initialize GitHub configuration.

        Args:
            server_url: GitHub API server URL (default: https://api.github.com)
            token_storage: TokenStorage instance for database-backed credentials
        """
        super().__init__(token_storage)
        self._server_url = server_url

        # Store per-user GitHub toolkits (in-memory cache)
        self._github_toolkits: dict[str, object] = {}

    def is_required(self) -> bool:
        """GitHub is an optional toolkit.

        Only prompts when user mentions GitHub/PRs.

        Returns:
            False (optional toolkit)
        """
        return False

    def is_configured(self, user_id: str) -> bool:
        """Check if GitHub is configured for user.

        Args:
            user_id: User identifier

        Returns:
            True if user has a valid GitHub token
        """
        logger.info(f"🔍 GitHubConfig.is_configured() called for user_id={user_id}")

        # Check database storage first (preferred)
        if self.token_storage:
            token_data = self.token_storage.get_github_token(user_id)
            if token_data:
                logger.info(f"✅ Found GitHub token in database for user {user_id}")
                return True
            else:
                logger.info(f"❌ No GitHub token in database for user {user_id}")

        # Fall back to legacy in-memory storage
        if user_id in self._user_configs and "github_token" in self._user_configs[user_id]:
            logger.info(f"✅ Found GitHub token in memory for user {user_id}")
            return True

        logger.info(f"❌ GitHub NOT configured for user {user_id}")
        return False

    def extract_and_store_config(self, message: str, user_id: str) -> str | None:
        """Extract and store GitHub token from user message.

        Supports patterns like:
        - "my github token is ghp_xxxxx"
        - "github token: ghp_xxxxx"
        - "github_token = ghp_xxxxx"
        - "set github token to ghp_xxxxx"
        - Standalone classic tokens (ghp_, gho_, ghu_, ghs_, ghr_ prefixes)
        - Standalone fine-grained tokens (github_pat_ prefix)

        Args:
            message: User message that may contain GitHub token
            user_id: User identifier

        Returns:
            Confirmation message if token was extracted and stored,
            None if no token found in message

        Raises:
            ValueError: If GitHub token is invalid
        """
        # Try to extract GitHub token
        token = self._extract_github_token(message)

        if not token:
            return None

        logger.info(f"Validating GitHub token for user {user_id}")

        try:
            # Import here to avoid circular dependency
            from agentllm.tools.github_toolkit import GitHubToolkit

            # Create toolkit with the token
            toolkit = GitHubToolkit(
                token=token,
                server_url=self._server_url,
            )

            # Validate the connection
            success, validation_message = toolkit.validate_connection()

            if not success:
                logger.error(f"GitHub token validation failed for user {user_id}: {validation_message}")
                raise ValueError(f"Invalid GitHub token: {validation_message}")

            logger.info(f"GitHub token validated successfully for user {user_id}")

            # Store the token in database if available, otherwise in memory
            if self.token_storage:
                success = self.token_storage.upsert_github_token(
                    user_id=user_id,
                    token=token,
                    server_url=self._server_url,
                )
                if success:
                    logger.info(f"✅ Stored GitHub token in database for user {user_id}")
                    # Verify it was stored
                    verify = self.token_storage.get_github_token(user_id)
                    if verify:
                        logger.info(f"✅ Verified token retrieval for user {user_id}")
                    else:
                        logger.error(f"❌ Failed to verify token for user {user_id}")
                else:
                    logger.error(f"❌ Failed to store GitHub token for user {user_id}")
            else:
                # Fall back to in-memory storage (legacy)
                if user_id not in self._user_configs:
                    self._user_configs[user_id] = {}
                self._user_configs[user_id]["github_token"] = token
                logger.info(f"Stored GitHub token in memory for user {user_id}")

            # Store the toolkit for this user (in-memory cache)
            self._github_toolkits[user_id] = toolkit
            logger.info(f"Cached GitHub toolkit for user {user_id}")

            # Return confirmation with validation message
            return (
                f"✅ GitHub configured successfully!\n\n"
                f"{validation_message}\n\n"
                f"You can now ask me to analyze pull requests and manage your review queue."
            )

        except Exception as e:
            logger.error(f"Failed to validate GitHub token for user {user_id}: {e}")
            raise ValueError(f"Failed to validate GitHub token: {str(e)}") from e

    def get_config_prompt(self, user_id: str) -> str | None:
        """Get prompt for GitHub token.

        Args:
            user_id: User identifier

        Returns:
            Prompt if not configured, None if configured
        """
        if self.is_configured(user_id):
            return None

        return (
            "🔑 **GitHub Configuration Required**\n\n"
            "To access GitHub, please provide your personal access token:\n\n"
            "Say: 'My GitHub token is YOUR_TOKEN_HERE'\n\n"
            "To create a GitHub personal access token:\n"
            "1. Go to https://github.com/settings/tokens\n"
            "2. Choose either:\n"
            "   - **Fine-grained token** (recommended): Click 'Generate new token (fine-grained)'\n"
            "     - Select repository access and permissions\n"
            "     - Token format: `github_pat_...`\n"
            "   - **Classic token**: Click 'Generate new token (classic)'\n"
            "     - Select scopes: `repo` (full control of private repositories)\n"
            "     - Token format: `ghp_...`\n"
            "3. Give it a descriptive name (e.g., 'AgentLLM Review Agent')\n"
            "4. Click 'Generate token' and copy it\n"
            "5. Send it to me in the format above\n\n"
            "**Note**: Keep your token secure and never share it publicly!"
        )

    def get_toolkit(self, user_id: str) -> object | None:
        """Get GitHub toolkit for user if configured.

        Args:
            user_id: User identifier

        Returns:
            GitHubToolkit instance if configured, None otherwise
        """
        # Return cached toolkit if available
        if user_id in self._github_toolkits:
            return self._github_toolkits[user_id]

        # If we have token but no toolkit (e.g., after restart), recreate it
        if not self.is_configured(user_id):
            return None

        # Recreate toolkit from database or memory
        toolkit = None
        if self.token_storage:
            # Get credentials from database
            try:
                from agentllm.tools.github_toolkit import GitHubToolkit

                token_data = self.token_storage.get_github_token(user_id)
                if not token_data:
                    logger.error(f"No GitHub token found in database for user {user_id}")
                    return None

                toolkit = GitHubToolkit(
                    token=token_data["token"],
                    server_url=token_data["server_url"],
                )
                logger.info(f"Recreated GitHub toolkit from database for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to create GitHub toolkit from database: {e}")
                return None
        else:
            # Use legacy in-memory authentication
            if user_id in self._user_configs and "github_token" in self._user_configs[user_id]:
                from agentllm.tools.github_toolkit import GitHubToolkit

                token = self._user_configs[user_id]["github_token"]
                toolkit = GitHubToolkit(
                    token=token,
                    server_url=self._server_url,
                )
                logger.info(f"Recreated GitHub toolkit (legacy) for user {user_id}")

        if toolkit:
            self._github_toolkits[user_id] = toolkit

        return toolkit

    def check_authorization_request(self, message: str, user_id: str) -> str | None:
        """Check if message requests GitHub access and prompt if needed.

        Args:
            message: User message
            user_id: User identifier

        Returns:
            GitHub token prompt if user needs to configure, None otherwise
        """
        logger.info(f"🔍 GitHubConfig.check_authorization_request() for user {user_id}")

        # Check if message mentions GitHub
        github_keywords = [
            "github",
            "pull request",
            "pr",
            "review",
            "repository",
            "repo",
        ]

        message_lower = message.lower()
        mentions_github = any(keyword in message_lower for keyword in github_keywords)

        if not mentions_github:
            logger.info(f"ℹ️ Message doesn't mention GitHub keywords - skipping")
            return None

        logger.info(f"🔍 Message mentions GitHub, checking if user {user_id} is configured")

        # Check if user already has GitHub configured
        if self.is_configured(user_id):
            logger.info(f"✅ User {user_id} has GitHub access - proceeding")
            return None

        # User needs to configure GitHub
        logger.info(f"⚠️ User {user_id} needs to configure GitHub - prompting")
        return self.get_config_prompt(user_id)

    def requires_agent_recreation(self, config_name: str) -> bool:
        """Check if this config requires agent recreation.

        GitHub token configuration adds new tools to the agent.

        Args:
            config_name: Configuration name

        Returns:
            True if config is github_token
        """
        return config_name == "github_token"

    def get_agent_instructions(self, user_id: str) -> list[str]:
        """Get GitHub-specific agent instructions.

        Args:
            user_id: User identifier

        Returns:
            List of instruction strings
        """
        if self.get_toolkit(user_id):
            return [
                f"You have access to GitHub tools to manage pull request reviews. "
                f"Use these tools when users ask about PR prioritization, review queues, or GitHub repositories."
            ]
        return []

    # Private helper methods

    def _extract_github_token(self, message: str) -> str | None:
        """Extract GitHub token from user message.

        Args:
            message: User message text

        Returns:
            Extracted token or None if not found
        """
        # Create flexible regex patterns
        config_name = "github_token"
        config_pattern = config_name.replace("_", "[ _-]")

        patterns = [
            # "my github token is VALUE"
            rf"(?:my\s+)?{config_pattern}\s+(?:is|=|:)\s+([^\s]+)",
            # "set github token to VALUE"
            rf"set\s+{config_pattern}\s+to\s+([^\s]+)",
            # "github token: VALUE" or "github_token: VALUE"
            rf"{config_pattern}:\s*([^\s]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1)

        # Try to detect standalone GitHub tokens
        # Classic tokens: ghp_ (personal), gho_ (OAuth), ghu_ (user-to-server),
        # ghs_ (server-to-server), ghr_ (refresh token)
        # Format: prefix + 36 alphanumeric characters
        classic_token_pattern = r"(?:^|\s)(gh[poushr]_[A-Za-z0-9]{36,})(?:\s|$)"
        match = re.search(classic_token_pattern, message)
        if match:
            return match.group(1)

        # Fine-grained tokens: github_pat_
        # Format: github_pat_ + base62 string (typically 22 chars) + _ + base62 string (typically 59 chars)
        # Total length varies but typically ~93 characters after the prefix
        fine_grained_token_pattern = r"(?:^|\s)(github_pat_[A-Za-z0-9_]{80,})(?:\s|$)"
        match = re.search(fine_grained_token_pattern, message)
        if match:
            return match.group(1)

        return None
