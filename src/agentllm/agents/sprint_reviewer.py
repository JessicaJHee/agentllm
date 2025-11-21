"""Sprint Reviewer agent for generating team sprint reviews."""

import os
from typing import Any

from agno.db.sqlite import SqliteDb

from agentllm.agents.base import AgentFactory, BaseAgentWrapper
from agentllm.agents.sprint_reviewer_configurator import SprintReviewerConfigurator
from agentllm.db import TokenStorage

# Map GEMINI_API_KEY to GOOGLE_API_KEY if not set
if "GOOGLE_API_KEY" not in os.environ and "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


class SprintReviewer(BaseAgentWrapper):
    """Sprint Reviewer with toolkit configuration management.

    This class extends BaseAgentWrapper to provide a Sprint Reviewer agent
    specialized for creating sprint reviews for development teams.

    Toolkit Configuration:
    ---------------------
    - Google Drive: OAuth-based access to read team mapping document (required)
    - JIRA: API token-based access to search sprint issues (required)

    The agent helps with:
    - Searching for issues in the current sprint for a specific team
    - Generating sprint review with metrics (tickets closed, bugs, stories/tasks closed)
    - Grouping issues by parent epic when multiple issues from same epic
    - Providing links to issues in the review
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
        """Initialize the Sprint Reviewer with configurator pattern.

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
    ) -> SprintReviewerConfigurator:
        """Create Sprint Reviewer configurator instance.

        Args:
            user_id: User identifier
            session_id: Session identifier
            shared_db: Shared database
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            SprintReviewerConfigurator instance
        """
        return SprintReviewerConfigurator(
            user_id=user_id,
            session_id=session_id,
            shared_db=shared_db,
            token_storage=self._token_storage,
            **kwargs,
        )


class SprintReviewerFactory(AgentFactory):
    """Factory for creating Sprint Reviewer instances.

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
    ) -> SprintReviewer:
        """Create a Sprint Reviewer instance.

        Args:
            shared_db: Shared database instance (SqliteDb)
            token_storage: Token storage instance (TokenStorage)
            user_id: User ID for this agent instance
            session_id: Optional session ID for conversation history
            temperature: Optional temperature parameter for the model
            max_tokens: Optional max tokens parameter for the model
            **kwargs: Additional keyword arguments for the agent

        Returns:
            SprintReviewer instance
        """
        return SprintReviewer(
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
            "name": "sprint-reviewer",
            "description": "Sprint review assistant",
            "mode": "chat",
            "requires_env": ["GEMINI_API_KEY"],
        }
