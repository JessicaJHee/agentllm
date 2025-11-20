"""Base agent wrapper class for LiteLLM integration with configurator pattern."""

import json
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from agno.agent import (
    Agent,
    ReasoningStepEvent,
    RunCompletedEvent,
    RunContentEvent,
    ToolCallCompletedEvent,
    ToolCallStartedEvent,
)
from agno.db.sqlite import SqliteDb
from loguru import logger

from agentllm.agents.base.configurator import AgentConfigurator


class BaseAgentWrapper(ABC):
    """Base class for agent wrappers using configurator pattern.

    This class provides common functionality for wrapping Agno agents with:
    - Configurator-based setup (configuration + agent building delegated)
    - Agent lifecycle management (caching per user+session)
    - Streaming/non-streaming execution
    - Provider-agnostic interface (yields LiteLLM GenericStreamingChunk format)

    Subclasses must implement _create_configurator() to provide agent-specific
    configurator instances.

    Architecture:
    - NO caching of wrappers (custom_handler.py caches wrapper instances)
    - Agent caching handled internally per wrapper instance
    - Configurator pattern separates config management from execution
    - Agno event processing (converts to LiteLLM format for custom_handler)
    """

    def __init__(
        self,
        shared_db: SqliteDb,
        user_id: str,
        session_id: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **model_kwargs: Any,
    ):
        """Initialize the agent wrapper.

        Args:
            shared_db: Shared database instance for session management
            user_id: User identifier (wrapper is per-user+session)
            session_id: Session identifier (optional)
            temperature: Model temperature (0.0-2.0)
            max_tokens: Maximum tokens in response
            **model_kwargs: Additional model parameters, including:
                - max_tool_result_length: Max chars for tool results in UI
                  (defaults to AGENTLLM_MAX_TOOL_RESULT_LENGTH env var, then None)
        """
        logger.debug("=" * 80)
        logger.info(f"{self.__class__.__name__}.__init__() called")
        logger.debug(
            f"Parameters: user_id={user_id}, session_id={session_id}, "
            f"temperature={temperature}, max_tokens={max_tokens}, model_kwargs={model_kwargs}"
        )

        # Store user and session identifiers
        self._user_id = user_id
        self._session_id = session_id

        # Configure UI display options with priority:
        # 1. Explicit kwarg (agent-specific override)
        # 2. Environment variable (global default)
        # 3. None (no truncation)
        max_tool_result_length = model_kwargs.pop("max_tool_result_length", None)
        if max_tool_result_length is None:
            # Check environment variable for global default
            env_limit = os.getenv("AGENTLLM_MAX_TOOL_RESULT_LENGTH")
            if env_limit is not None:
                try:
                    max_tool_result_length = int(env_limit)
                    logger.debug(f"Using AGENTLLM_MAX_TOOL_RESULT_LENGTH={max_tool_result_length} from env")
                except ValueError:
                    logger.warning(f"Invalid AGENTLLM_MAX_TOOL_RESULT_LENGTH='{env_limit}', ignoring")

        self._max_tool_result_length = max_tool_result_length
        logger.debug(f"Tool result truncation: {max_tool_result_length or 'disabled'}")

        # Create configurator (subclass-specific)
        logger.debug("Creating configurator...")
        self._configurator = self._create_configurator(
            user_id=user_id,
            session_id=session_id,
            shared_db=shared_db,
            temperature=temperature,
            max_tokens=max_tokens,
            **model_kwargs,
        )
        logger.info(f"Created {self._configurator.__class__.__name__}")

        # Store single Agno agent instance for this wrapper
        # Note: This wrapper is already per-user+session (cached in custom_handler),
        # so we only need one agent instance
        self._agent: Agent | None = None

        logger.info(f"✅ {self.__class__.__name__} initialization complete")
        logger.debug("=" * 80)

    # ========== ABSTRACT METHODS (SUBCLASS REQUIRED) ==========

    @abstractmethod
    def _create_configurator(
        self,
        user_id: str,
        session_id: str | None,
        shared_db: SqliteDb,
        **kwargs: Any,
    ) -> AgentConfigurator:
        """Create configurator instance for this agent.

        Args:
            user_id: User identifier
            session_id: Session identifier
            shared_db: Shared database
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            AgentConfigurator instance
        """
        pass

    # ========== CONCRETE METHODS (SHARED IMPLEMENTATION) ==========

    def _format_reasoning_content(self, content: str) -> str:
        """Format reasoning content with markdown block quotes for Open WebUI.

        Args:
            content: Raw reasoning/thinking content

        Returns:
            Formatted string with markdown block quotes
        """
        lines = content.split("\n")
        formatted = []
        for line in lines:
            if line.strip():
                formatted.append(f"> {line}")
            else:
                formatted.append(">")
        return "\n".join(formatted)

    def _format_tool_result(self, result: Any) -> str:
        """Format tool result with optional truncation and JSON formatting for Open WebUI.

        Args:
            result: Raw tool result (can be dict, list, str, or any object)

        Returns:
            Formatted string with optional truncation and JSON syntax highlighting
        """
        # Convert to string first (handles all types)
        result_str = str(result) if not isinstance(result, str) else result

        # Try to detect and format JSON (whether it's a dict/list or JSON string)
        is_json = False
        json_content = None

        # Case 1: Result is already a dict or list
        if isinstance(result, (dict, list)):
            try:
                json_content = json.dumps(result, indent=2, ensure_ascii=False)
                is_json = True
            except (TypeError, ValueError) as e:
                logger.debug(f"Failed to JSON-serialize dict/list: {e}")

        # Case 2: Result is a string that might be JSON
        elif isinstance(result, str):
            # Try to parse as JSON to validate
            try:
                parsed = json.loads(result)
                # Re-serialize with nice formatting
                json_content = json.dumps(parsed, indent=2, ensure_ascii=False)
                is_json = True
            except (json.JSONDecodeError, TypeError, ValueError):
                # Not valid JSON, treat as plain text
                pass

        # Format based on whether it's JSON or plain text
        if is_json and json_content:
            # Apply truncation to JSON
            if self._max_tool_result_length and len(json_content) > self._max_tool_result_length:
                original_length = len(json_content)
                json_content = json_content[: self._max_tool_result_length]
                truncation_notice = f"\n\n... (truncated, {original_length:,} chars total)"
                # Return with JSON code block
                return f"```json\n{json_content}{truncation_notice}\n```"
            else:
                return f"```json\n{json_content}\n```"
        else:
            # Plain text: apply truncation if needed
            if self._max_tool_result_length and len(result_str) > self._max_tool_result_length:
                original_length = len(result_str)
                result_str = result_str[: self._max_tool_result_length]
                result_str += f"\n\n... (truncated, {original_length:,} chars total)"
            return result_str

    def _get_or_create_agent(self) -> Agent:
        """Get or create the underlying Agno agent.

        Uses configurator to build agent if not cached.

        Returns:
            The Agno agent instance
        """
        logger.debug("=" * 80)
        logger.info(f"_get_or_create_agent() called for user_id={self._user_id}")

        # Return existing agent if available (cache hit)
        if self._agent is not None:
            logger.info("✓ Using CACHED agent (wrapper is per-user+session)")
            logger.debug("=" * 80)
            return self._agent

        # Create new agent using configurator (cache miss)
        logger.info("✗ Cache MISS - Creating NEW agent via configurator")
        agent = self._configurator.build_agent()

        # Store the agent for reuse
        self._agent = agent
        logger.debug("Agent stored in wrapper instance")
        logger.debug("=" * 80)

        return agent

    def _invalidate_agent_cache(self) -> None:
        """Invalidate cached agent instance.

        Called when configuration changes to force agent rebuild.
        """
        if self._agent is not None:
            logger.info("⚠ Invalidating cached agent due to config change")
            self._agent = None
            self._configurator.invalidate()
        else:
            logger.debug("No cached agent to invalidate")

    def run(self, message: str, user_id: str | None = None, session_id: str | None = None, **kwargs) -> Any:
        """Run the agent with configuration management (synchronous).

        Flow:
        1. Check if user is configured (via configurator)
        2. If not configured, handle configuration (extract tokens or prompt)
        3. If configured, create agent (if needed) and run it

        Args:
            message: User message
            user_id: User identifier from OpenWebUI
            session_id: Session identifier for conversation isolation
            **kwargs: Additional arguments to pass to wrapped agent

        Returns:
            RunResponse from agent or configuration prompt
        """
        logger.info("=" * 80)
        logger.info(f">>> {self.__class__.__name__}.run() STARTED")
        logger.info(f"user_id={user_id}, session_id={session_id}, message_len={len(message)}")

        # Check configuration and handle if needed (via configurator)
        logger.info("Checking configuration...")
        config_response = self._configurator.handle_configuration(message)

        if config_response is not None:
            logger.info("Configuration handling returned response")
            # Check if we need to invalidate agent cache
            self._invalidate_agent_cache()
            logger.info(f"<<< {self.__class__.__name__}.run() FINISHED (config response)")
            logger.info("=" * 80)
            return config_response

        # User is configured, get/create agent and run it
        try:
            logger.info(f"Creating agent for user {self._user_id}...")
            agent = self._get_or_create_agent()

            # Use provided session_id or fall back to instance session_id
            effective_session_id = session_id if session_id is not None else self._session_id

            logger.info(f"Running agent.run() for user {self._user_id}, session {effective_session_id}...")
            result = agent.run(message, user_id=self._user_id, session_id=effective_session_id, **kwargs)
            logger.info(f"✅ Agent.run() completed, result type: {type(result)}")
            logger.info(f"<<< {self.__class__.__name__}.run() FINISHED (success)")
            logger.info("=" * 80)
            return result
        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            logger.error(f"Failed to run agent for user {self._user_id}: {e}", exc_info=True)
            logger.info(f"<<< {self.__class__.__name__}.run() FINISHED (exception)")
            logger.info("=" * 80)
            return self._configurator._create_simple_response(error_msg)

    async def _arun_non_streaming(self, message: str, user_id: str | None = None, session_id: str | None = None, **kwargs):
        """Internal async method for non-streaming mode - returns async generator.

        This method handles configuration and agent lifecycle, then returns the async generator
        from agent.arun(). The iteration/consumption is handled separately by
        _consume_non_streaming_result(), maintaining structural alignment with the synchronous
        run() method.

        Flow:
        1. Check configuration (return config prompt if needed)
        2. Get/create agent instance
        3. Call agent.arun() and return the async generator

        Args:
            message: User message
            user_id: User identifier
            session_id: Session identifier for conversation isolation
            **kwargs: Additional arguments to pass to agent

        Returns:
            Async generator from agent.arun()
        """
        logger.info("=" * 80)
        logger.info(f">>> {self.__class__.__name__}._arun_non_streaming() STARTED")
        logger.info(f"user_id={user_id}, session_id={session_id}")

        # Check configuration
        config_response = self._configurator.handle_configuration(message)

        if config_response is not None:
            self._invalidate_agent_cache()
            logger.info(f"<<< {self.__class__.__name__}._arun_non_streaming() FINISHED (config response)")
            logger.info("=" * 80)
            return config_response

        try:
            agent = self._get_or_create_agent()
            effective_session_id = session_id if session_id is not None else self._session_id

            logger.info(f"Calling agent.arun() for user {self._user_id}, session {effective_session_id}...")
            # agent.arun() returns an async generator - return it for consumption
            stream = agent.arun(message, user_id=self._user_id, session_id=effective_session_id, **kwargs)

            logger.info("✅ Agent.arun() called, returning async generator")
            logger.info(f"<<< {self.__class__.__name__}._arun_non_streaming() FINISHED (success)")
            logger.info("=" * 80)
            return stream
        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            logger.error(f"Failed to run agent: {e}", exc_info=True)
            logger.info(f"<<< {self.__class__.__name__}._arun_non_streaming() FINISHED (exception)")
            logger.info("=" * 80)
            return self._configurator._create_simple_response(error_msg)

    async def _consume_non_streaming_result(self, message: str, user_id: str | None = None, session_id: str | None = None, **kwargs):
        """Consume async generator from _arun_non_streaming and return final result.

        This method separates the concern of stream consumption from agent lifecycle management.
        It aligns the async path structure with the synchronous run() method, where iteration
        is handled separately from the core agent execution logic.

        Flow:
        1. Call _arun_non_streaming() to get async generator
        2. Iterate through all events to consume the stream
        3. Return the final result (last event from stream)

        Args:
            message: User message
            user_id: User identifier
            session_id: Session identifier for conversation isolation
            **kwargs: Additional arguments to pass to agent

        Returns:
            Final RunOutput from the agent stream
        """
        logger.debug("_consume_non_streaming_result() called")

        # Get the async generator from _arun_non_streaming
        stream = await self._arun_non_streaming(message, user_id, session_id, **kwargs)

        # If config response (not a generator), return it directly
        if not hasattr(stream, "__aiter__"):
            return stream

        # Iterate through all events to get the final RunOutput
        final_result = None
        async for event in stream:
            # The last event should be a RunOutput object
            final_result = event

        if final_result is None:
            raise RuntimeError("No response received from agent")

        logger.debug(f"_consume_non_streaming_result() completed, result type: {type(final_result)}")
        return final_result

    async def _arun_streaming(
        self, message: str, user_id: str | None = None, session_id: str | None = None, **kwargs
    ) -> AsyncIterator[dict[str, Any]]:
        """Internal async generator for streaming mode.

        Converts Agno events to LiteLLM GenericStreamingChunk format.

        Yields:
            GenericStreamingChunk dictionaries with text field
        """
        logger.info("=" * 80)
        logger.info(f">>> {self.__class__.__name__}._arun_streaming() STARTED")
        logger.info(f"user_id={user_id}, session_id={session_id}")

        # Check configuration
        config_response = self._configurator.handle_configuration(message)

        if config_response is not None:
            self._invalidate_agent_cache()

            # Yield config message as GenericStreamingChunk
            yield {
                "text": config_response.content,
                "finish_reason": None,
                "index": 0,
                "is_finished": False,
                "tool_use": None,
                "usage": {"completion_tokens": 0, "prompt_tokens": 0, "total_tokens": 0},
            }

            # Yield final chunk
            yield {
                "text": "",
                "finish_reason": "stop",
                "index": 0,
                "is_finished": True,
                "tool_use": None,
                "usage": {"completion_tokens": 0, "prompt_tokens": 0, "total_tokens": 0},
            }

            logger.info(f"<<< {self.__class__.__name__}._arun_streaming() FINISHED (config response)")
            logger.info("=" * 80)
            return

        try:
            agent = self._get_or_create_agent()
            effective_session_id = session_id if session_id is not None else self._session_id

            logger.info(f"Starting agent.arun() streaming for user {self._user_id}, session {effective_session_id}...")
            chunk_count = 0

            # Get the async generator from agent.arun()
            stream = agent.arun(
                message,
                stream=True,
                stream_events=True,
                user_id=self._user_id,
                session_id=effective_session_id,
                **kwargs,
            )

            # Track reasoning state
            reasoning_start_time = None
            reasoning_content_parts = []
            reasoning_block_sent = False

            try:
                async for chunk in stream:
                    chunk_count += 1
                    chunk_type = type(chunk).__name__

                    logger.debug(f"Received event #{chunk_count}: type={chunk_type}")

                    if isinstance(chunk, RunContentEvent):
                        # Handle Gemini native thinking content
                        if hasattr(chunk, "reasoning_content") and chunk.reasoning_content:
                            if reasoning_start_time is None:
                                import time

                                reasoning_start_time = time.time()
                                logger.info("💭 Reasoning started")

                            reasoning_content_parts.append(chunk.reasoning_content)
                            continue

                        content = chunk.content if hasattr(chunk, "content") else str(chunk)

                        if not content:
                            continue

                        # Send accumulated reasoning if any
                        if reasoning_content_parts and not reasoning_block_sent:
                            import time

                            reasoning_duration = int(time.time() - reasoning_start_time) if reasoning_start_time else 0
                            full_reasoning_content = "".join(reasoning_content_parts)
                            formatted_reasoning = self._format_reasoning_content(full_reasoning_content)

                            reasoning_block = (
                                f'<details type="reasoning" done="true" duration="{reasoning_duration}">\n'
                                f"<summary>Thought for {reasoning_duration} seconds</summary>\n\n"
                                f"{formatted_reasoning}\n\n"
                                f"</details>\n\n"
                            )

                            yield {
                                "text": reasoning_block,
                                "finish_reason": None,
                                "index": 0,
                                "is_finished": False,
                                "tool_use": None,
                                "usage": {"completion_tokens": 0, "prompt_tokens": 0, "total_tokens": 0},
                            }

                            reasoning_block_sent = True

                        # Yield regular content
                        yield {
                            "text": content,
                            "finish_reason": None,
                            "index": 0,
                            "is_finished": False,
                            "tool_use": None,
                            "usage": {"completion_tokens": 0, "prompt_tokens": 0, "total_tokens": 0},
                        }

                    elif isinstance(chunk, ToolCallStartedEvent):
                        if hasattr(chunk, "tool") and chunk.tool:
                            tool = chunk.tool
                            tool_name = tool.tool_name if hasattr(tool, "tool_name") else "unknown"
                            logger.info(f"🔧 ToolCallStartedEvent: {tool_name}")

                    elif isinstance(chunk, ToolCallCompletedEvent):
                        if hasattr(chunk, "tool") and chunk.tool:
                            tool = chunk.tool
                            tool_name = tool.tool_name if hasattr(tool, "tool_name") else "unknown"
                            tool_args = tool.tool_args if hasattr(tool, "tool_args") else {}
                            tool_result = tool.result if hasattr(tool, "result") else "No result"

                            logger.info(f"✅ ToolCallCompletedEvent: {tool_name}")

                            # Format arguments as JSON
                            args_json = json.dumps(tool_args, indent=2, ensure_ascii=False) if tool_args else "{}"

                            # Format result with truncation and JSON detection
                            formatted_result = self._format_tool_result(tool_result)

                            completion_text = (
                                f'\n<details type="tool_call" open="true">\n'
                                f"<summary>🔧 Tool: {tool_name}</summary>\n\n"
                                f"**Arguments:**\n```json\n{args_json}\n```\n\n"
                                f"**Result:**\n\n{formatted_result}\n\n"
                                f"✅ Completed\n</details>\n\n"
                            )

                            yield {
                                "text": completion_text,
                                "finish_reason": None,
                                "index": 0,
                                "is_finished": False,
                                "tool_use": None,
                                "usage": {"completion_tokens": 0, "prompt_tokens": 0, "total_tokens": 0},
                            }

                    elif isinstance(chunk, ReasoningStepEvent):
                        reasoning_text = (
                            chunk.reasoning_content
                            if hasattr(chunk, "reasoning_content")
                            else str(chunk.content)
                            if hasattr(chunk, "content")
                            else ""
                        )

                        if reasoning_text:
                            logger.info("💭 ReasoningStepEvent")
                            reasoning_block = (
                                f'\n<details type="reasoning">\n<summary>💭 Reasoning Step</summary>\n\n{reasoning_text}\n\n</details>\n\n'
                            )

                            yield {
                                "text": reasoning_block,
                                "finish_reason": None,
                                "index": 0,
                                "is_finished": False,
                                "tool_use": None,
                                "usage": {"completion_tokens": 0, "prompt_tokens": 0, "total_tokens": 0},
                            }

                    elif isinstance(chunk, RunCompletedEvent):
                        logger.info("✓ RunCompletedEvent received!")
                        break

            except StopAsyncIteration:
                logger.info("Stream ended via StopAsyncIteration")
            except Exception as e:
                logger.error(f"Error during stream iteration: {e}", exc_info=True)
                raise

            # Send final chunk
            logger.info("Sending final chunk")
            yield {
                "text": "",
                "finish_reason": "stop",
                "index": 0,
                "is_finished": True,
                "tool_use": None,
                "usage": {"completion_tokens": chunk_count, "prompt_tokens": 0, "total_tokens": chunk_count},
            }

            logger.info(f"<<< {self.__class__.__name__}._arun_streaming() FINISHED (success)")
            logger.info("=" * 80)

        except Exception as e:
            error_msg = f"❌ Error: {str(e)}"
            logger.error(f"Failed to stream from agent: {e}", exc_info=True)

            yield {
                "text": error_msg,
                "finish_reason": None,
                "index": 0,
                "is_finished": False,
                "tool_use": None,
                "usage": {"completion_tokens": 0, "prompt_tokens": 0, "total_tokens": 0},
            }

            yield {
                "text": "",
                "finish_reason": "stop",
                "index": 0,
                "is_finished": True,
                "tool_use": None,
                "usage": {"completion_tokens": 0, "prompt_tokens": 0, "total_tokens": 0},
            }

            logger.info(f"<<< {self.__class__.__name__}._arun_streaming() FINISHED (exception)")
            logger.info("=" * 80)

    def arun(self, message: str, user_id: str | None = None, session_id: str | None = None, stream: bool = False, **kwargs):
        """Run the agent asynchronously with configuration management.

        Args:
            message: User message
            user_id: User identifier
            session_id: Session identifier for conversation isolation
            stream: Whether to stream responses
            **kwargs: Additional arguments to pass to wrapped agent

        Returns:
            Coroutine[RunResponse] (non-streaming) or AsyncIterator of GenericStreamingChunk dicts (streaming)
        """
        logger.debug(f"arun() called with stream={stream}")

        if stream:
            return self._arun_streaming(message, user_id, session_id, **kwargs)
        else:
            logger.debug("Delegating to _consume_non_streaming_result()")
            # Return coroutine that consumes stream and returns final result
            return self._consume_non_streaming_result(message, user_id, session_id, **kwargs)
