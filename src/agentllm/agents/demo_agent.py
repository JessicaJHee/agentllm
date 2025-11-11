"""
Demo Agent - A simple example agent for showcasing AgentLLM features.

This agent demonstrates:
- Required configuration flow (favorite color)
- Simple utility tools (color palette generation)
- Extensive logging for debugging and education
- Session memory and conversation history
- Streaming and non-streaming responses
"""

import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from agno.agent import Agent, RunCompletedEvent, RunContentEvent
from agno.db.sqlite import SqliteDb
from agno.models.google import Gemini
from loguru import logger

from agentllm.agents.toolkit_configs.favorite_color_config import FavoriteColorConfig
from agentllm.db import TokenStorage
from agentllm.tools.color_toolkit import ColorTools

# Map GEMINI_API_KEY to GOOGLE_API_KEY if not set
if "GOOGLE_API_KEY" not in os.environ and "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

# Shared database for all agents to enable session management
DB_PATH = Path("tmp/agno_sessions.db")
DB_PATH.parent.mkdir(exist_ok=True)
shared_db = SqliteDb(db_file=str(DB_PATH))

# Create token storage using the shared database
token_storage = TokenStorage(agno_db=shared_db)


class DemoAgent:
    """
    Demo Agent for showcasing AgentLLM platform features.

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
    - Extensive logging throughout execution flow

    The agent maintains the same interface as Agno Agent, making it
    transparent to LiteLLM and other callers.
    """

    def __init__(
        self,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **model_kwargs: Any,
    ):
        """
        Initialize the Demo Agent with toolkit configurations.

        Args:
            temperature: Model temperature (0.0-2.0)
            max_tokens: Maximum tokens in response
            **model_kwargs: Additional model parameters
        """
        logger.debug("=" * 80)
        logger.info("DemoAgent.__init__() called")
        logger.debug(f"Parameters: temperature={temperature}, max_tokens={max_tokens}, model_kwargs={model_kwargs}")

        # Initialize toolkit configurations
        logger.debug("Initializing FavoriteColorConfig...")
        color_config = FavoriteColorConfig(token_storage=token_storage)

        self.toolkit_configs = [
            color_config,  # Required: user must configure before using agent
        ]

        logger.info(f"Initialized {len(self.toolkit_configs)} toolkit config(s)")

        # Store model parameters for later agent creation
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._model_kwargs: dict[str, Any] = model_kwargs

        logger.debug("Stored model parameters for agent creation")

        # Store agents per user_id (agents are not shared across users)
        self._agents: dict[str, Agent] = {}

        logger.info("✅ DemoAgent initialization complete")
        logger.debug("=" * 80)

    def _invalidate_agent(self, user_id: str) -> None:
        """
        Invalidate cached agent for a user.

        This forces agent recreation on next request, useful when
        user configures/changes their favorite color.

        Args:
            user_id: User identifier
        """
        logger.debug("=" * 80)
        logger.debug(f"_invalidate_agent() called for user_id={user_id}")

        if user_id in self._agents:
            logger.info(f"⚠ Invalidating cached agent for user {user_id}")
            del self._agents[user_id]
            logger.debug(f"Agent removed from cache. Remaining cached agents: {len(self._agents)}")
        else:
            logger.debug(f"No cached agent found for user {user_id} (nothing to invalidate)")

        logger.debug("=" * 80)

    def _check_and_invalidate_agent(self, config_name: str, user_id: str) -> None:
        """
        Check if config requires agent recreation and invalidate if needed.

        Args:
            config_name: Configuration name that was just stored
            user_id: User identifier
        """
        logger.debug(f"_check_and_invalidate_agent() called for config_name={config_name}, user_id={user_id}")

        # Check if any toolkit config requires agent recreation for this config
        for config in self.toolkit_configs:
            if config.requires_agent_recreation(config_name):
                self._invalidate_agent(user_id)
                logger.info(f"Config '{config_name}' requires agent recreation for user {user_id}")
                break

    def _get_or_create_agent(self, user_id: str) -> Agent:
        """
        Get or create the underlying Agno agent for a specific user.

        Agents are created per-user and include their configured toolkits.

        Args:
            user_id: User identifier

        Returns:
            The Agno agent instance for this user
        """
        logger.debug("=" * 80)
        logger.info(f"_get_or_create_agent() called for user_id={user_id}")

        # Return existing agent for this user if available
        if user_id in self._agents:
            logger.info(f"✓ Using CACHED agent for user {user_id}")
            logger.debug("=" * 80)
            return self._agents[user_id]

        # Create the agent for this user
        logger.info(f"✗ Cache MISS - Creating NEW agent for user {user_id}")

        # Build model parameters
        logger.debug("Building model parameters...")
        model_params: dict[str, Any] = {"id": "gemini-2.5-flash"}
        if self._temperature is not None:
            model_params["temperature"] = self._temperature
            logger.debug(f"  + temperature: {self._temperature}")
        if self._max_tokens is not None:
            # Gemini uses max_output_tokens instead of max_tokens
            model_params["max_output_tokens"] = self._max_tokens
            logger.debug(f"  + max_output_tokens: {self._max_tokens}")
        model_params.update(self._model_kwargs)
        logger.debug(f"Final model params: {model_params}")

        # Collect all configured toolkits for this user
        logger.debug("Collecting configured toolkits...")
        tools = []

        # Get favorite color from config to create ColorTools
        color_config = self.toolkit_configs[0]  # FavoriteColorConfig
        if color_config.is_configured(user_id):
            favorite_color = color_config.get_user_color(user_id)
            if favorite_color is not None:
                logger.info(f"  ✓ User {user_id} has favorite color configured: {favorite_color}")

                # Create ColorTools with user's favorite color
                logger.debug(f"  Creating ColorTools with favorite_color={favorite_color}")
                color_tools = ColorTools(favorite_color=favorite_color)
                tools.append(color_tools)
                logger.info(f"  ✓ Added ColorTools to agent for user {user_id}")
            else:
                logger.warning(f"  ⚠ User {user_id} is configured but color is None (unexpected)")
        else:
            logger.warning(f"  ⚠ User {user_id} doesn't have favorite color configured (this shouldn't happen)")

        logger.debug(f"Total tools collected: {len(tools)}")

        # Create base instructions
        logger.debug("Building base instructions...")
        instructions = [
            "You are the **Demo Agent** - a simple example agent designed to showcase AgentLLM platform features.",
            "",
            "🎯 **Your Purpose:**",
            "- Demonstrate required configuration flow (favorite color)",
            "- Showcase simple utility tools (color palettes)",
            "- Illustrate session memory and conversation history",
            "- Provide educational examples with clear explanations",
            "",
            "🛠 **Your Capabilities:**",
            "- Generate color palettes (complementary, analogous, monochromatic)",
            "- Format text with color-themed styling",
            "- Explain your own architecture and configuration",
            "- Maintain conversation history across sessions",
            "",
            "💬 **Communication Style:**",
            "- Be friendly and educational",
            "- Use markdown formatting for clarity",
            "- Explain what you're doing when using tools",
            "- Reference the user's favorite color when relevant",
            "",
            "📚 **Educational Notes:**",
            "- You are a DEMO agent - your primary purpose is to showcase features",
            "- When users ask about your implementation, be transparent",
            "- You can explain: configuration flow, tool creation, logging, session management",
            "- Point users to relevant code files when discussing architecture",
            "",
            "🎨 **About the Favorite Color Configuration:**",
            "- This demonstrates the **required configuration pattern**",
            "- Users must configure their favorite color before you can assist them",
            "- The configuration is stored per-user and persists across sessions",
            "- Changing the favorite color recreates your agent with updated tools",
        ]

        # Add toolkit-specific instructions
        logger.debug("Adding toolkit-specific instructions...")
        for config in self.toolkit_configs:
            toolkit_instructions = config.get_agent_instructions(user_id)
            if toolkit_instructions:
                logger.debug(f"  + {config.__class__.__name__} added {len(toolkit_instructions)} instruction lines")
                instructions.extend(toolkit_instructions)

        logger.debug(f"Total instruction lines: {len(instructions)}")

        # Create Agno Agent instance
        logger.debug("Creating Agno Agent instance...")
        agent = Agent(
            name="demo-agent",
            model=Gemini(**model_params),
            description="A demo agent showcasing AgentLLM features",
            instructions=instructions,
            markdown=True,
            tools=tools if tools else None,
            # Session management - enables conversation history
            db=shared_db,
            add_history_to_context=True,
            num_history_runs=10,  # Include last 10 messages
            read_chat_history=True,  # Allow agent to read full history
        )

        logger.info("✅ Agno Agent instance created successfully")

        # Cache the agent for this user
        self._agents[user_id] = agent
        logger.info(f"✅ Created and cached agent for user {user_id} with {len(tools)} tool(s). Total cached agents: {len(self._agents)}")
        logger.debug("=" * 80)

        return agent

    def _create_simple_response(self, content: str) -> Any:
        """
        Create a simple response object that mimics Agno's RunResponse.

        Args:
            content: Message content to return

        Returns:
            Response object with content attribute
        """
        logger.debug(f"_create_simple_response() called with content length: {len(content)}")

        class SimpleResponse:
            def __init__(self, content):
                self.content = content

        response = SimpleResponse(content)
        logger.debug("Created SimpleResponse object")
        return response

    def _handle_configuration(self, message: str, user_id: str | None) -> Any | None:
        """
        Handle toolkit configuration from user messages.

        This method implements a three-phase configuration check:
        1. Extract and store: Try to extract configuration from message
        2. Check required: If any required toolkit is unconfigured, prompt user
        3. Check optional: If optional toolkit detects authorization request, prompt

        Args:
            message: User's message
            user_id: User identifier

        Returns:
            SimpleResponse with prompt/confirmation if config handling needed,
            None if all checks passed (proceed to agent)
        """
        logger.debug("=" * 80)
        logger.info(f">>> _handle_configuration() STARTED - user_id={user_id}")
        logger.debug(f"Message length: {len(message)}")

        if not user_id:
            logger.warning("user_id is None, cannot handle configuration")
            logger.info("<<< _handle_configuration() FINISHED (no user_id)")
            logger.debug("=" * 80)
            return None

        # Phase 1: Try to extract and store configuration from message
        logger.info("📝 Phase 1: Attempting to extract configuration from message")
        for config in self.toolkit_configs:
            config_name = config.__class__.__name__
            logger.debug(f"  Checking {config_name}...")

            try:
                confirmation = config.extract_and_store_config(message, user_id)
                if confirmation:
                    logger.info(f"✅ {config_name} extracted and stored configuration")
                    logger.debug(f"Confirmation message: {confirmation[:100]}...")

                    # Check if this config requires agent recreation
                    self._check_and_invalidate_agent(config_name.lower().replace("config", ""), user_id)

                    logger.info("<<< _handle_configuration() FINISHED (config stored)")
                    logger.debug("=" * 80)
                    return self._create_simple_response(confirmation)
                else:
                    logger.debug(f"  {config_name} did not extract configuration")
            except ValueError as e:
                # Invalid configuration (e.g., invalid color)
                error_msg = f"❌ Configuration Error: {str(e)}"
                logger.warning(f"{config_name} validation failed: {e}")
                logger.info("<<< _handle_configuration() FINISHED (validation error)")
                logger.debug("=" * 80)
                return self._create_simple_response(error_msg)

        logger.debug("No configuration extracted from message")

        # Phase 2: Check if any required toolkits are unconfigured
        logger.info("🔍 Phase 2: Checking required toolkit configurations")
        for config in self.toolkit_configs:
            if config.is_required() and not config.is_configured(user_id):
                config_name = config.__class__.__name__
                logger.info(f"⚠ Required toolkit {config_name} is NOT configured for user {user_id}")

                prompt = config.get_config_prompt(user_id)
                if prompt:
                    logger.info(f"Returning configuration prompt for {config_name}")
                    logger.debug(f"Prompt: {prompt[:100]}...")
                    logger.info("<<< _handle_configuration() FINISHED (required config prompt)")
                    logger.debug("=" * 80)
                    return self._create_simple_response(prompt)

        logger.debug("All required toolkits are configured")

        # Phase 3: Check if optional toolkits detect authorization requests
        logger.info("🔍 Phase 3: Checking optional toolkit authorization requests")
        for config in self.toolkit_configs:
            if not config.is_required():
                config_name = config.__class__.__name__
                logger.debug(f"  Checking optional toolkit {config_name}...")

                auth_prompt = config.check_authorization_request(message, user_id)
                if auth_prompt:
                    logger.info(f"Optional toolkit {config_name} detected authorization request")
                    logger.debug(f"Auth prompt: {auth_prompt[:100]}...")
                    logger.info("<<< _handle_configuration() FINISHED (optional config prompt)")
                    logger.debug("=" * 80)
                    return self._create_simple_response(auth_prompt)

        # No configuration handling needed, proceed to agent
        logger.info("✓ All configuration checks passed, proceeding to agent")
        logger.info("<<< _handle_configuration() FINISHED (proceed to agent)")
        logger.debug("=" * 80)
        return None

    def run(self, message: str, user_id: str | None = None, **kwargs) -> Any:
        """
        Run the agent with configuration management (synchronous).

        Flow:
        1. Check if user is configured
        2. If not configured, handle configuration (extract tokens or prompt)
        3. If configured, create agent (if needed) and run it

        Args:
            message: User message
            user_id: User identifier from OpenWebUI
            **kwargs: Additional arguments to pass to wrapped agent

        Returns:
            RunResponse from agent or configuration prompt
        """
        logger.info("=" * 80)
        logger.info(f">>> DemoAgent.run() STARTED - user_id={user_id}")
        logger.info(f"Message length: {len(message)}, kwargs: {kwargs}")

        # Check configuration and handle if needed
        logger.info("Checking configuration...")
        config_response = self._handle_configuration(message, user_id)

        # If config_response is not None, user needs to configure
        if config_response is not None:
            logger.info("Configuration handling returned response, returning to user")
            logger.info("<<< DemoAgent.run() FINISHED (config response)")
            logger.info("=" * 80)
            return config_response

        # User is configured, get/create agent and run it
        if not user_id:
            error_msg = "❌ User ID is required to create an agent."
            logger.error("Cannot create agent: user_id is None")
            logger.info("<<< DemoAgent.run() FINISHED (error)")
            logger.info("=" * 80)
            return self._create_simple_response(error_msg)

        try:
            logger.info(f"Getting or creating agent for user {user_id}...")
            agent = self._get_or_create_agent(user_id)
            logger.info(f"Running agent.run() for user {user_id}...")
            result = agent.run(message, user_id=user_id, **kwargs)
            logger.info(f"✅ Agent.run() completed, result type: {type(result)}")
            logger.info("<<< DemoAgent.run() FINISHED (success)")
            logger.info("=" * 80)
            return result
        except Exception as e:
            # Agent creation or execution failed
            error_msg = f"❌ Error: {str(e)}"
            logger.error(f"Failed to run agent for user {user_id}: {e}", exc_info=True)
            logger.info("<<< DemoAgent.run() FINISHED (exception)")
            logger.info("=" * 80)
            return self._create_simple_response(error_msg)

    async def _arun_non_streaming(self, message: str, user_id: str | None = None, **kwargs):
        """Internal async method for non-streaming mode."""
        logger.info("=" * 80)
        logger.info(f">>> DemoAgent._arun_non_streaming() STARTED - user_id={user_id}")
        logger.info(f"Message length: {len(message)}, kwargs: {kwargs}")

        # Check configuration and handle if needed
        logger.info("Checking configuration...")
        config_response = self._handle_configuration(message, user_id)

        if config_response is not None:
            logger.info("Configuration handling returned response, returning to user")
            logger.info("<<< DemoAgent._arun_non_streaming() FINISHED (config response)")
            logger.info("=" * 80)
            return config_response

        if not user_id:
            error_msg = "❌ User ID is required to create an agent."
            logger.error("Cannot create agent: user_id is None")
            logger.info("<<< DemoAgent._arun_non_streaming() FINISHED (error)")
            logger.info("=" * 80)
            return self._create_simple_response(error_msg)

        try:
            logger.info(f"Getting or creating agent for user {user_id}...")
            agent = self._get_or_create_agent(user_id)
            logger.info(f"Running agent.arun() for user {user_id} (non-streaming)...")
            result = await agent.arun(message, user_id=user_id, **kwargs)
            logger.info(f"✅ Agent.arun() completed, result type: {type(result)}")
            logger.info("<<< DemoAgent._arun_non_streaming() FINISHED (success)")
            logger.info("=" * 80)
            return result
        except Exception as e:
            # Agent creation or execution failed
            error_msg = f"❌ Error: {str(e)}"
            logger.error(f"Failed to run agent for user {user_id}: {e}", exc_info=True)
            logger.info("<<< DemoAgent._arun_non_streaming() FINISHED (exception)")
            logger.info("=" * 80)
            return self._create_simple_response(error_msg)

    async def _arun_streaming(self, message: str, user_id: str | None = None, **kwargs) -> AsyncIterator:
        """Internal async method for streaming mode."""
        logger.info("=" * 80)
        logger.info(f">>> DemoAgent._arun_streaming() STARTED - user_id={user_id}")
        logger.info(f"Message length: {len(message)}, kwargs: {kwargs}")

        # Check configuration and handle if needed
        logger.info("Checking configuration...")
        config_response = self._handle_configuration(message, user_id)

        if config_response is not None:
            logger.info("Configuration handling returned response, yielding to user")
            logger.info("<<< DemoAgent._arun_streaming() FINISHED (config response)")
            logger.info("=" * 80)
            # Yield the configuration message as content so it gets displayed
            yield RunContentEvent(content=config_response.content)
            # Signal completion
            yield RunCompletedEvent(content="")
            return

        if not user_id:
            error_msg = "❌ User ID is required to create an agent."
            logger.error("Cannot create agent: user_id is None")
            logger.info("<<< DemoAgent._arun_streaming() FINISHED (error)")
            logger.info("=" * 80)
            # Yield error message as content so it gets displayed
            yield RunContentEvent(content=error_msg)
            # Signal completion
            yield RunCompletedEvent(content="")
            return

        try:
            logger.info(f"Getting or creating agent for user {user_id}...")
            agent = self._get_or_create_agent(user_id)
            logger.info(f"Running agent.arun(stream=True) for user {user_id}...")

            # Stream events from agent
            # Use stream_events=True to get all events (not just final response)
            event_count = 0
            async for event in agent.arun(message, user_id=user_id, stream=True, stream_events=True, **kwargs):
                event_count += 1
                event_type = type(event).__name__

                # Log every event for educational purposes
                logger.debug(f"  Event #{event_count}: {event_type}")

                # Filter out RunCompletedEvent (it's a control signal, not content)
                if isinstance(event, RunCompletedEvent):
                    logger.debug(f"  Event #{event_count}: RunCompletedEvent received (not yielding)")
                    break

                # Yield all content events
                yield event

            logger.info(f"✅ Agent.arun(stream=True) completed, {event_count} events yielded")
            logger.info("<<< DemoAgent._arun_streaming() FINISHED (success)")
            logger.info("=" * 80)

        except Exception as e:
            # Agent creation or execution failed
            error_msg = f"❌ Error: {str(e)}"
            logger.error(f"Failed to stream from agent for user {user_id}: {e}", exc_info=True)
            logger.info("<<< DemoAgent._arun_streaming() FINISHED (exception)")
            logger.info("=" * 80)
            # Yield error message as content so it gets displayed
            yield RunContentEvent(content=error_msg)
            # Signal completion
            yield RunCompletedEvent(content="")

    def arun(self, message: str, user_id: str | None = None, stream: bool = False, **kwargs):
        """
        Run the agent asynchronously with configuration management.

        Args:
            message: User message
            user_id: User identifier
            stream: Whether to stream responses
            **kwargs: Additional arguments to pass to wrapped agent

        Returns:
            Coroutine[RunResponse] (non-streaming) or AsyncIterator of events (streaming)
        """
        logger.debug(f"arun() called with stream={stream}")

        if stream:
            logger.debug("Delegating to _arun_streaming()")
            # Return async generator directly for streaming
            return self._arun_streaming(message, user_id, **kwargs)
        else:
            logger.debug("Delegating to _arun_non_streaming()")
            # Return coroutine for non-streaming (caller must await)
            return self._arun_non_streaming(message, user_id, **kwargs)
