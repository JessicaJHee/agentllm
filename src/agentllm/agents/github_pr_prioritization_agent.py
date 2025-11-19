"""
GitHub Review Prioritization Agent - Intelligent PR review queue management.

This agent helps developers manage their PR review workload using multi-factor
prioritization algorithms to suggest which PRs to review next.
"""

import os
from typing import Any

from agno.db.sqlite import SqliteDb

from agentllm.agents.base import AgentFactory, BaseAgentWrapper
from agentllm.agents.github_pr_prioritization_agent_configurator import GitHubReviewAgentConfigurator
from agentllm.db import TokenStorage

# Map GEMINI_API_KEY to GOOGLE_API_KEY if not set
if "GOOGLE_API_KEY" not in os.environ and "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


class GitHubReviewAgent(BaseAgentWrapper):
    """GitHub PR Prioritization Agent.

    This agent specializes in helping developers manage their PR review queue
    by intelligently prioritizing pull requests based on multiple factors:
    - Age (older PRs get priority to avoid staleness)
    - Size (smaller PRs are easier to review)
    - Discussion activity (comments suggest urgency)
    - Labels (urgent/hotfix/blocking boost priority)
    - Author patterns (first-time contributors get attention)

    Key Features:
    - Multi-factor PR scoring algorithm (0-80 scale)
    - Priority tiers: CRITICAL, HIGH, MEDIUM, LOW
    - Review queue management
    - Repository velocity tracking
    - Smart review suggestions with reasoning

    Toolkit Configuration:
    - GitHub: Personal access token for repository access (optional)

    Architecture (NEW):
    - Uses configurator pattern for clean separation of concerns
    - GitHubReviewAgentConfigurator handles configuration management
    - GitHubReviewAgent (BaseAgentWrapper) handles execution
    - GitHubReviewAgentFactory enables plugin system registration
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
        """Initialize the GitHub Review Agent with configurator pattern.

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
    ) -> GitHubReviewAgentConfigurator:
        """Create GitHub Review Agent configurator instance.

        Args:
            user_id: User identifier
            session_id: Session identifier
            shared_db: Shared database
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            GitHubReviewAgentConfigurator instance
        """
        return GitHubReviewAgentConfigurator(
            user_id=user_id,
            session_id=session_id,
            shared_db=shared_db,
            token_storage=self._token_storage,
            **kwargs,
        )


class GitHubReviewAgentFactory(AgentFactory):
    """Factory for creating GitHub PR Prioritization Agent instances.

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
    ) -> GitHubReviewAgent:
        """Create a GitHub Review Agent instance.

        Args:
            shared_db: Shared database instance (SqliteDb)
            token_storage: Token storage instance (TokenStorage)
            user_id: User ID for this agent instance
            session_id: Optional session ID for conversation history
            temperature: Optional temperature parameter for the model
            max_tokens: Optional max tokens parameter for the model
            **kwargs: Additional keyword arguments for the agent

        Returns:
            GitHubReviewAgent instance
        """
        return GitHubReviewAgent(
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
            "name": "github-pr-prioritization",
            "description": "GitHub PR prioritization agent with intelligent review queue management",
            "mode": "chat",
            "requires_env": ["GEMINI_API_KEY"],  # or GOOGLE_API_KEY
        }
