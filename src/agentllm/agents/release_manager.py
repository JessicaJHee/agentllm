"""Release Manager agent for managing software releases and changelogs."""

import os
from typing import Any

from agno.db.sqlite import SqliteDb

from agentllm.agents.base import AgentFactory, BaseAgentWrapper
from agentllm.agents.release_manager_configurator import ReleaseManagerConfigurator
from agentllm.db import TokenStorage

# Map GEMINI_API_KEY to GOOGLE_API_KEY if not set
if "GOOGLE_API_KEY" not in os.environ and "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


class ReleaseManager(BaseAgentWrapper):
    """Release Manager with toolkit configuration management.

    This class extends BaseAgentWrapper to provide a Release Manager agent
    specialized for Red Hat Developer Hub (RHDH) release management.

    Toolkit Configuration:
    ---------------------
    - Google Drive: OAuth-based access to Google Docs, Sheets, and Presentations (required)
    - JIRA: API token-based access to JIRA issues (optional)
    - SystemPromptExtension: Extended instructions from Google Drive document (required if configured)

    The agent helps with:
    - Managing Y-stream releases (major versions like 1.7.0, 1.8.0)
    - Managing Z-stream releases (maintenance versions like 1.6.1, 1.6.2)
    - Tracking release progress, risks, and blockers
    - Coordinating with Engineering, QE, Documentation, and Product Management teams
    - Providing release status updates for meetings
    - Monitoring Jira for release-related issues, features, and bugs
    """

    def __init__(
        self,
        shared_db: SqliteDb,
        token_storage: TokenStorage,
        user_id: str,
        session_id: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        system_prompt_local_file: str | None = None,
        **model_kwargs,
    ):
        """Initialize the Release Manager with configurator pattern.

        Args:
            shared_db: Shared database instance for session management
            token_storage: Token storage instance for credentials
            user_id: User identifier (wrapper is per-user+session)
            session_id: Session identifier (optional)
            temperature: Model temperature (0.0-2.0)
            max_tokens: Maximum tokens in response
            system_prompt_local_file: Optional local file path for system prompt.
                                      If provided, reads from file instead of Google Drive.
                                      Useful for testing without OAuth.
            **model_kwargs: Additional model parameters
        """
        # Store token_storage for configurator
        self._token_storage = token_storage
        # Store local file path for system prompt extension
        self._system_prompt_local_file = system_prompt_local_file

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
    ) -> ReleaseManagerConfigurator:
        """Create Release Manager configurator instance.

        Args:
            user_id: User identifier
            session_id: Session identifier
            shared_db: Shared database
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            ReleaseManagerConfigurator instance
        """
        return ReleaseManagerConfigurator(
            user_id=user_id,
            session_id=session_id,
            shared_db=shared_db,
            token_storage=self._token_storage,
            system_prompt_local_file=self._system_prompt_local_file,
            **kwargs,
        )


class ReleaseManagerFactory(AgentFactory):
    """Factory for creating Release Manager instances.

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
    ) -> ReleaseManager:
        """Create a Release Manager instance.

        Args:
            shared_db: Shared database instance (SqliteDb)
            token_storage: Token storage instance (TokenStorage)
            user_id: User ID for this agent instance
            session_id: Optional session ID for conversation history
            temperature: Optional temperature parameter for the model
            max_tokens: Optional max tokens parameter for the model
            **kwargs: Additional keyword arguments for the agent

        Returns:
            ReleaseManager instance
        """
        return ReleaseManager(
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
            "name": "release-manager",
            "description": "Release Manager for Red Hat Developer Hub (RHDH)",
            "mode": "chat",
            "requires_env": ["GEMINI_API_KEY"],
        }
