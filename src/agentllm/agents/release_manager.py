"""Release Manager agent for managing software releases and changelogs."""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.google import Gemini

# Map GEMINI_API_KEY to GOOGLE_API_KEY if not set
if "GOOGLE_API_KEY" not in os.environ and "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

# Shared database for all agents to enable session management
DB_PATH = Path("tmp/agno_sessions.db")
DB_PATH.parent.mkdir(exist_ok=True)
shared_db = SqliteDb(db_file=str(DB_PATH))


class ReleaseManager:
    """Release Manager with authentication and configuration management.

    This class wraps an Agno agent and manages user-specific configuration tokens
    (e.g., Jira tokens). It intercepts run() and arun() calls to:
    1. Extract configuration tokens from user messages
    2. Store tokens per user_id in memory
    3. Prompt users for missing configurations
    4. Delegate to the wrapped agent once configured

    The class maintains the same interface as Agno Agent, making it transparent
    to LiteLLM and other callers.
    """

    def __init__(
        self,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **model_kwargs,
    ):
        """Initialize the Release Manager with authentication.

        Args:
            temperature: Model temperature (0.0-2.0)
            max_tokens: Maximum tokens in response
            **model_kwargs: Additional model parameters
        """
        # Store model parameters for later agent creation
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._model_kwargs = model_kwargs

        # Agent will be created after configuration is complete
        self._agent: Optional[Agent] = None

        # Configuration management (POC: in-memory storage)
        self._required_configs = {
            "jira_token": (
                "Please provide your Jira token by saying: "
                "'My Jira token is YOUR_TOKEN_HERE'"
            )
        }
        # Store configs per user: {user_id: {config_name: value}}
        # Note: Currently in-memory. To migrate to database, modify store_config()
        self._user_configs: Dict[str, Dict[str, str]] = {}

    def _get_or_create_agent(self) -> Agent:
        """Get or create the underlying Agno agent.

        Agent is only created after successful configuration. This method is
        idempotent - subsequent calls return the same agent instance.

        Returns:
            The underlying Agno agent instance
        """
        if self._agent is None:
            # Create the agent now that configuration is complete
            model_params = {"id": "gemini-2.5-flash"}
            if self._temperature is not None:
                model_params["temperature"] = self._temperature
            if self._max_tokens is not None:
                model_params["max_tokens"] = self._max_tokens
            model_params.update(self._model_kwargs)

            self._agent = Agent(
                name="release-manager",
                model=Gemini(**model_params),
                description=(
                    "A release management assistant that helps with software "
                    "releases, changelogs, and version planning"
                ),
                instructions=[
                    "You are an expert release manager and software engineering assistant.",
                    "Help users plan releases, create changelogs, manage versions, "
                    "and coordinate deployment activities.",
                    "Provide guidance on semantic versioning, release notes, and "
                    "best practices.",
                    "Be thorough in analyzing changes and their impact on users.",
                    "Use markdown formatting for structured output.",
                ],
                markdown=True,
                # Session management
                db=shared_db,
                add_history_to_context=True,
                num_history_runs=10,  # Include last 10 messages
                read_chat_history=True,  # Allow agent to read full history
            )

        return self._agent

    def is_configured(self, user_id: Optional[str]) -> bool:
        """Check if user has all required configurations.

        Args:
            user_id: User identifier

        Returns:
            True if all required configs are present for this user
        """
        if not user_id:
            return False

        if user_id not in self._user_configs:
            return False

        user_config = self._user_configs[user_id]
        return all(config_name in user_config for config_name in self._required_configs)

    def get_missing_configs(self, user_id: Optional[str]) -> List[str]:
        """Get list of missing configuration names for a user.

        Args:
            user_id: User identifier

        Returns:
            List of config names that are missing
        """
        if not user_id or user_id not in self._user_configs:
            return list(self._required_configs.keys())

        user_config = self._user_configs[user_id]
        return [
            config_name
            for config_name in self._required_configs
            if config_name not in user_config
        ]

    def extract_token_from_message(self, message: str) -> Optional[Dict[str, str]]:
        """Extract configuration tokens from user message using regex patterns.

        Supports patterns like:
        - "my jira token is abc123"
        - "jira token: abc123"
        - "jira_token = abc123"
        - "set jira token to abc123"

        Args:
            message: User message text

        Returns:
            Dict mapping config_name to extracted value, or None if no match
        """
        if not message:
            return None

        # Try to extract each required config from the message
        extracted = {}

        for config_name in self._required_configs:
            # Create flexible regex patterns for this config
            # Handle both "jira token" and "jira_token" formats
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
                    extracted[config_name] = match.group(1)
                    break

        return extracted if extracted else None

    def store_config(self, user_id: str, config_name: str, value: str) -> None:
        """Store a configuration value for a user.

        Note: Currently stores in-memory. To migrate to database storage,
        modify this method to write to DB instead.

        Args:
            user_id: User identifier
            config_name: Name of the configuration (e.g., "jira_token")
            value: Configuration value to store
        """
        if user_id not in self._user_configs:
            self._user_configs[user_id] = {}

        self._user_configs[user_id][config_name] = value

    def _build_prompt_message(self, user_id: Optional[str]) -> str:
        """Build a prompt message for missing configurations.

        Args:
            user_id: User identifier

        Returns:
            Formatted prompt message
        """
        missing = self.get_missing_configs(user_id)

        if not missing:
            return ""

        # Build a friendly prompt with instructions for each missing config
        prompt_parts = ["I need some configuration before I can help you:\n"]

        for config_name in missing:
            prompt_msg = self._required_configs.get(config_name, "")
            prompt_parts.append(f"- {prompt_msg}")

        return "\n".join(prompt_parts)

    def _build_confirmation_message(self, stored_configs: Dict[str, str]) -> str:
        """Build a confirmation message after storing configs.

        Args:
            stored_configs: Dict of config names to values that were stored

        Returns:
            Confirmation message
        """
        config_names = ", ".join(stored_configs.keys())

        message = f"✅ Thank you! I've securely stored your {config_names}.\n\n"

        # Check if user is now fully configured
        if len(stored_configs) == len(self._required_configs):
            message += "You're all set! How can I help you?"
        else:
            message += "I still need a few more configurations. Please provide them to continue."

        return message

    def _create_simple_response(self, content: str) -> Any:
        """Create a simple response object that mimics Agno's RunResponse.

        Args:
            content: Message content to return

        Returns:
            Response object with content attribute
        """

        class SimpleResponse:
            def __init__(self, content: str):
                self.content = content

            def __str__(self):
                return self.content

        return SimpleResponse(content)

    def _handle_configuration(
        self, message: str, user_id: Optional[str]
    ) -> Optional[Any]:
        """Handle configuration extraction and validation.

        This method:
        1. First checks if user is fully configured
        2. If yes, returns None (proceed to agent)
        3. If not, tries to extract tokens from the message
        4. If tokens found, stores them and returns confirmation
        5. If no tokens found, returns prompt for missing configs

        Args:
            message: User message
            user_id: User identifier

        Returns:
            Response with configuration message, or None if fully configured
        """
        # First check if user is already fully configured
        if self.is_configured(user_id):
            # User is configured, proceed to agent
            return None

        # User not configured - try to extract configuration tokens from message
        extracted = self.extract_token_from_message(message)

        if extracted:
            # Store all extracted configs
            for config_name, value in extracted.items():
                if user_id:
                    self.store_config(user_id, config_name, value)

            # Return confirmation message
            confirmation = self._build_confirmation_message(extracted)
            return self._create_simple_response(confirmation)

        # No tokens extracted, prompt user for missing configs
        prompt = self._build_prompt_message(user_id)
        return self._create_simple_response(prompt)

    # def run(self, message: str, user_id: Optional[str] = None, **kwargs) -> Any:
    #     """Run the agent with configuration management.

    #     Flow:
    #     1. Check if user is configured
    #     2. If not configured, handle configuration (extract tokens or prompt)
    #     3. If configured, create agent (if needed) and run it

    #     Args:
    #         message: User message
    #         user_id: User identifier from OpenWebUI
    #         **kwargs: Additional arguments to pass to wrapped agent

    #     Returns:
    #         RunResponse from agent or configuration prompt
    #     """
    #     # Check configuration and handle if needed
    #     config_response = self._handle_configuration(message, user_id)

    #     # If config_response is not None, user needs to configure
    #     if config_response is not None:
    #         return config_response

    #     # User is configured, get/create agent and run it
    #     agent = self._get_or_create_agent()
    #     return agent.run(message, user_id=user_id, **kwargs)

    async def arun(self, message: str, user_id: Optional[str] = None, **kwargs):
        """Async version of run() with same configuration management logic.

        Handles both streaming and non-streaming modes. When streaming is enabled
        and user needs configuration, yields a single chunk with the config message.

        Args:
            message: User message
            user_id: User identifier from OpenWebUI
            **kwargs: Additional arguments to pass to wrapped agent

        Returns:
            RunResponse from agent, configuration prompt, or async iterator (if streaming)
        """
        # Check if streaming mode
        stream = kwargs.get("stream", False)

        # TEMPORARY: Skip config check to test agent pass-through
        # Check configuration and handle if needed
        # config_response = self._handle_configuration(message, user_id)
        config_response = None  # TEMPORARY: Always return None

        # If config_response is not None, user needs to configure
        if config_response is not None:
            if stream:
                # In streaming mode, we need to yield the config response as chunks
                async def config_stream():
                    content = (
                        config_response.content
                        if hasattr(config_response, "content")
                        else str(config_response)
                    )
                    yield content

                return config_stream()
            else:
                # Non-streaming mode, return the response directly
                return config_response

        # User is configured, get/create agent and run it
        agent = self._get_or_create_agent()

        # Return the agent's arun result directly - it handles streaming internally
        # Don't await here - just pass through what the agent returns
        return agent.arun(message, user_id=user_id, **kwargs)
