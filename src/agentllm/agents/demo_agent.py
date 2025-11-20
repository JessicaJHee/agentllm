"""
Demo Agent - A simple example agent for showcasing AgentLLM features.

This agent demonstrates:
- Required configuration flow (favorite color)
- Simple utility tools (color palette generation)
- Extensive logging for debugging and education
- Session memory and conversation history
- Streaming and non-streaming responses

Architecture (NEW):
- Uses configurator pattern for clean separation of concerns
- DemoAgentConfigurator handles configuration management
- DemoAgent (BaseAgentWrapper) handles execution
- DemoAgentFactory enables plugin system registration
"""

import os
from typing import Any

from agno.db.sqlite import SqliteDb

from agentllm.agents.base import AgentFactory, BaseAgentWrapper
from agentllm.agents.demo_agent_configurator import DemoAgentConfigurator
from agentllm.db import TokenStorage

# Map GEMINI_API_KEY to GOOGLE_API_KEY if not set
if "GOOGLE_API_KEY" not in os.environ and "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


class DemoAgent(BaseAgentWrapper):
    """Demo Agent for showcasing AgentLLM platform features.

    This agent is intentionally simple and well-documented to serve as:
    1. A reference implementation for creating new agents
    2. A demonstration of the platform's capabilities
    3. An educational tool with extensive logging

    Key Features Demonstrated:
    - Required toolkit configuration (FavoriteColorConfig)
    - Simple utility tools (ColorTools)
    - Session memory and conversation history
    - Streaming and non-streaming responses
    - Per-user agent isolation
    - Configuration validation and error handling
    - Extensive logging throughout execution flow (inherited from base)
    - NEW: Configurator pattern for clean architecture

    The agent extends BaseAgentWrapper, which provides all common functionality.
    This class only implements agent-specific customizations via the configurator.
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
        """Initialize the Demo Agent with configurator pattern.

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
    ) -> DemoAgentConfigurator:
        """Create Demo Agent configurator instance.

        Args:
            user_id: User identifier
            session_id: Session identifier
            shared_db: Shared database
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            DemoAgentConfigurator instance
        """
        return DemoAgentConfigurator(
            user_id=user_id,
            session_id=session_id,
            shared_db=shared_db,
            token_storage=self._token_storage,
            **kwargs,
        )


class DemoAgentFactory(AgentFactory):
    """Factory for creating Demo Agent instances.

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
    ) -> DemoAgent:
        """Create a Demo Agent instance.

        Args:
            shared_db: Shared database instance (SqliteDb)
            token_storage: Token storage instance (TokenStorage)
            user_id: User ID for this agent instance
            session_id: Optional session ID for conversation history
            temperature: Optional temperature parameter for the model
            max_tokens: Optional max tokens parameter for the model
            **kwargs: Additional keyword arguments for the agent

        Returns:
            DemoAgent instance
        """
        # Set demo-specific UI truncation (overrides env var if set)
        # This keeps knowledge search results clean in the UI
        kwargs.setdefault("max_tool_result_length", 500)

        return DemoAgent(
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
            "name": "demo-agent",
            "description": "Demo agent showcasing AgentLLM features with interactive color tools",
            "mode": "chat",
            "requires_env": ["GEMINI_API_KEY"],  # or GOOGLE_API_KEY
        }
