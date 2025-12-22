"""Jira Triager agent for automatic team and component assignment.

This agent uses logic-based triage with component mappings and keyword analysis
to recommend team and component assignments for Jira tickets.
"""

import os
from typing import Any

from agno.db.sqlite import SqliteDb

from agentllm.agents.base import AgentFactory, BaseAgentWrapper
from agentllm.agents.jira_triager_configurator import JiraTriagerConfigurator
from agentllm.db import TokenStorage

# Map GEMINI_API_KEY to GOOGLE_API_KEY if not set
if "GOOGLE_API_KEY" not in os.environ and "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


class JiraTriager(BaseAgentWrapper):
    """Jira Triager agent for automatic team and component assignment.

    Uses logic-based triage with component mappings, keyword analysis, and assignee
    validation to recommend Jira ticket assignments.

    Required Configuration:
    - Jira: API token (user provides in chat)
    - Configuration: Local file OR Google Drive
    - JIRA_TRIAGER_SYSTEM_PROMPT_GDRIVE_URL: Google Doc with triage guidelines (optional)
    - JIRA_TRIAGER_GDRIVE_FOLDER_ID: Google Drive folder with rhdh-teams.json (for interactive mode)
    - JIRA_TRIAGER_CONFIG_FILE: Local path to rhdh-teams.json (for automation mode)

    See docs/agents/jira_triager_automation.md for setup instructions.
    """

    def __init__(
        self,
        shared_db: SqliteDb,
        token_storage: TokenStorage,
        user_id: str,
        session_id: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **model_kwargs,
    ):
        """Initialize the Jira Triager with configurator pattern.

        Args:
            shared_db: Shared database instance for session management
            token_storage: Token storage instance for credentials
            user_id: User identifier (wrapper is per-user+session)
            session_id: Session identifier (optional)
            temperature: Model temperature (0.0-2.0)
            max_tokens: Maximum tokens in response
            **model_kwargs: Additional model parameters
        """
        # Store token_storage for configurator
        self._token_storage = token_storage

        # Call parent constructor (will call _create_configurator)
        super().__init__(
            shared_db=shared_db,
            user_id=user_id,
            session_id=session_id,
            temperature=temperature,
            max_tokens=max_tokens,
            **model_kwargs,
        )

    def _create_configurator(
        self,
        user_id: str,
        session_id: str | None,
        shared_db: SqliteDb,
        **kwargs: Any,
    ) -> JiraTriagerConfigurator:
        """Create Jira Triager configurator instance.

        Args:
            user_id: User identifier
            session_id: Session identifier
            shared_db: Shared database
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            JiraTriagerConfigurator instance
        """
        return JiraTriagerConfigurator(
            user_id=user_id,
            session_id=session_id,
            shared_db=shared_db,
            token_storage=self._token_storage,
            **kwargs,
        )


class JiraTriagerFactory(AgentFactory):
    """Factory for creating Jira Triager instances.

    Registered via entry points in pyproject.toml for plugin system.
    """

    @staticmethod
    def create_agent(
        shared_db: Any,
        token_storage: Any,
        user_id: str,
        session_id: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> JiraTriager:
        """Create a Jira Triager instance.

        Args:
            shared_db: Shared database instance (SqliteDb)
            token_storage: Token storage instance (TokenStorage)
            user_id: User ID for this agent instance
            session_id: Optional session ID for conversation history
            temperature: Optional temperature parameter for the model
            max_tokens: Optional max tokens parameter for the model
            **kwargs: Additional keyword arguments for the agent

        Returns:
            JiraTriager instance
        """
        return JiraTriager(
            shared_db=shared_db,
            token_storage=token_storage,
            user_id=user_id,
            session_id=session_id,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    @staticmethod
    def get_metadata() -> dict[str, Any]:
        """Get agent metadata for proxy configuration.

        Returns:
            Dictionary with agent metadata
        """
        return {
            "name": "jira-triager",
            "description": "AI agent that recommends team and component assignments for Jira tickets",
            "mode": "chat",
            "requires_env": ["GEMINI_API_KEY"],
        }
