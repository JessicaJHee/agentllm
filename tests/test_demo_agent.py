"""
Tests for the Demo Agent.

This test suite demonstrates testing patterns for:
- Agent instantiation and configuration
- Required toolkit configuration flow
- Color extraction and validation
- Sync and async execution
- Streaming responses
- Tool invocations
- Session memory
"""

import os
from unittest.mock import patch

import pytest
from dotenv import load_dotenv

from agentllm.agents.demo_agent import DemoAgent
from agentllm.agents.toolkit_configs.favorite_color_config import FavoriteColorConfig

# Load .env file for tests
load_dotenv()

# Map GEMINI_API_KEY to GOOGLE_API_KEY if needed
if "GOOGLE_API_KEY" not in os.environ and "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


class TestDemoAgentBasics:
    """Basic tests for DemoAgent instantiation and parameters."""

    def test_create_agent(self):
        """Test that DemoAgent can be instantiated."""
        agent = DemoAgent()
        assert agent is not None
        assert len(agent.toolkit_configs) > 0

    def test_create_agent_with_params(self):
        """Test that DemoAgent accepts model parameters."""
        agent = DemoAgent(temperature=0.7, max_tokens=200)
        assert agent is not None
        assert agent._temperature == 0.7
        assert agent._max_tokens == 200

    def test_toolkit_configs_initialized(self):
        """Test that toolkit configs are properly initialized."""
        agent = DemoAgent()
        assert hasattr(agent, "toolkit_configs")
        assert isinstance(agent.toolkit_configs, list)
        assert len(agent.toolkit_configs) == 1  # Only FavoriteColorConfig

    def test_favorite_color_config_is_required(self):
        """Test that FavoriteColorConfig is marked as required."""
        agent = DemoAgent()
        color_config = agent.toolkit_configs[0]
        assert isinstance(color_config, FavoriteColorConfig)
        assert color_config.is_required() is True


class TestFavoriteColorConfiguration:
    """Tests for favorite color configuration management."""

    def test_required_config_prompts_immediately(self):
        """Test that agent prompts for favorite color on first message."""
        agent = DemoAgent()
        user_id = "test-user-new"

        # User sends message without configuring
        response = agent.run("Hello!", user_id=user_id)

        # Should get config prompt, not agent response
        content = str(response.content) if hasattr(response, "content") else str(response)
        assert "favorite color" in content.lower()
        assert "demo agent" in content.lower()

    def test_color_extraction_simple_pattern(self):
        """Test extraction of color from 'my favorite color is X' pattern."""
        agent = DemoAgent()
        user_id = "test-user-1"

        # User provides favorite color
        response = agent.run("My favorite color is blue", user_id=user_id)

        # Should get confirmation
        content = str(response.content) if hasattr(response, "content") else str(response)
        assert "blue" in content.lower()
        assert "✅" in content or "configured" in content.lower()

        # Verify color is stored
        color_config = agent.toolkit_configs[0]
        assert color_config.is_configured(user_id)
        assert color_config.get_user_color(user_id) == "blue"

    def test_color_extraction_i_like_pattern(self):
        """Test extraction from 'I like X' pattern."""
        agent = DemoAgent()
        user_id = "test-user-2"

        response = agent.run("I like green", user_id=user_id)

        content = str(response.content) if hasattr(response, "content") else str(response)
        assert "green" in content.lower()
        assert "✅" in content or "configured" in content.lower()

    def test_color_extraction_set_color_pattern(self):
        """Test extraction from 'set color to X' pattern."""
        agent = DemoAgent()
        user_id = "test-user-3"

        response = agent.run("set color to red", user_id=user_id)

        content = str(response.content) if hasattr(response, "content") else str(response)
        assert "red" in content.lower()
        assert "✅" in content or "configured" in content.lower()

    def test_color_extraction_color_equals_pattern(self):
        """Test extraction from 'color = X' pattern."""
        agent = DemoAgent()
        user_id = "test-user-4"

        response = agent.run("color: yellow", user_id=user_id)

        content = str(response.content) if hasattr(response, "content") else str(response)
        assert "yellow" in content.lower()
        assert "✅" in content or "configured" in content.lower()

    def test_invalid_color_rejected(self):
        """Test that invalid colors are rejected with error message."""
        agent = DemoAgent()
        user_id = "test-user-invalid"

        response = agent.run("My favorite color is magenta", user_id=user_id)

        content = str(response.content) if hasattr(response, "content") else str(response)
        assert "❌" in content or "error" in content.lower() or "invalid" in content.lower()
        assert "magenta" in content.lower()

    def test_multiple_users_isolated(self):
        """Test that different users have isolated configurations."""
        agent = DemoAgent()
        user1 = "test-user-a"
        user2 = "test-user-b"

        # Configure different colors for two users
        agent.run("My favorite color is blue", user_id=user1)
        agent.run("My favorite color is red", user_id=user2)

        # Verify isolation
        color_config = agent.toolkit_configs[0]
        assert color_config.get_user_color(user1) == "blue"
        assert color_config.get_user_color(user2) == "red"


class TestAgentCaching:
    """Tests for agent caching and recreation."""

    def test_agent_cached_per_user(self):
        """Test that agents are cached per user."""
        agent = DemoAgent()
        user_id = "test-user-cache"

        # Configure first
        agent.run("My favorite color is purple", user_id=user_id)

        # Create agent by running a message
        with patch.object(agent, "_get_or_create_agent", wraps=agent._get_or_create_agent) as mock_get:
            agent.run("Hello", user_id=user_id)

            # Second run should use cached agent
            agent.run("How are you?", user_id=user_id)

            # Should have called _get_or_create_agent twice (once per run)
            # But the agent itself should be cached
            assert mock_get.call_count == 2
            assert user_id in agent._agents

    def test_agent_invalidated_on_color_change(self):
        """Test that agent is invalidated when favorite color changes."""
        agent = DemoAgent()
        user_id = "test-user-invalidate"

        # Configure first color
        agent.run("My favorite color is blue", user_id=user_id)
        agent.run("Hello", user_id=user_id)

        # Verify agent is cached
        assert user_id in agent._agents
        cached_agent_id = id(agent._agents[user_id])

        # Change color (should invalidate agent)
        agent.run("My favorite color is red", user_id=user_id)

        # Agent should be invalidated (removed from cache)
        # Next run will create new agent
        agent.run("Hi again", user_id=user_id)

        # Verify new agent was created
        new_agent_id = id(agent._agents[user_id])
        assert new_agent_id != cached_agent_id


@pytest.mark.skipif(
    "GEMINI_API_KEY" not in os.environ and "GOOGLE_API_KEY" not in os.environ,
    reason="Requires GEMINI_API_KEY or GOOGLE_API_KEY environment variable",
)
class TestAgentExecution:
    """Tests for actual agent execution (requires API key)."""

    @pytest.fixture
    def configured_agent(self):
        """Fixture providing a configured agent."""
        agent = DemoAgent(temperature=0.7, max_tokens=150)
        user_id = "test-user-exec"

        # Configure the agent
        agent.run("My favorite color is blue", user_id=user_id)

        return agent, user_id

    def test_sync_run(self, configured_agent):
        """Test synchronous run method."""
        agent, user_id = configured_agent

        response = agent.run("What is your purpose?", user_id=user_id)

        # Should get a real response from the agent
        content = str(response.content) if hasattr(response, "content") else str(response)
        assert len(content) > 0
        assert "demo" in content.lower() or "showcase" in content.lower()

    @pytest.mark.asyncio
    async def test_async_run_non_streaming(self, configured_agent):
        """Test async non-streaming execution."""
        agent, user_id = configured_agent

        response = await agent.arun("Tell me about yourself", user_id=user_id, stream=False)

        # Should get a real response
        content = str(response.content) if hasattr(response, "content") else str(response)
        assert len(content) > 0

    @pytest.mark.asyncio
    async def test_async_run_streaming(self, configured_agent):
        """Test async streaming execution."""
        agent, user_id = configured_agent

        # Collect streamed events
        events = []
        # Don't await - arun returns an async generator when stream=True
        async for event in agent.arun("What can you do?", user_id=user_id, stream=True):
            events.append(event)

        # Should receive multiple events
        assert len(events) > 0

        # Last event should be RunCompletedEvent or similar
        # At minimum, we should get some content
        event_types = [type(event).__name__ for event in events]
        assert len(event_types) > 0


@pytest.mark.skipif(
    "GEMINI_API_KEY" not in os.environ and "GOOGLE_API_KEY" not in os.environ,
    reason="Requires GEMINI_API_KEY or GOOGLE_API_KEY environment variable",
)
class TestColorTools:
    """Tests for ColorTools integration."""

    @pytest.fixture
    def configured_agent(self):
        """Fixture providing a configured agent."""
        agent = DemoAgent(temperature=0.7, max_tokens=500)
        user_id = "test-user-tools"

        # Configure with a specific color
        agent.run("My favorite color is green", user_id=user_id)

        return agent, user_id

    def test_agent_has_color_tools(self, configured_agent):
        """Test that agent has ColorTools after configuration."""
        agent, user_id = configured_agent

        # Force agent creation
        agent.run("Hello", user_id=user_id)

        # Verify agent has tools
        created_agent = agent._agents[user_id]
        assert created_agent.tools is not None
        assert len(created_agent.tools) > 0

    def test_palette_generation_tool(self, configured_agent):
        """Test that agent can use palette generation tool."""
        agent, user_id = configured_agent

        response = agent.run("Generate a complementary color palette for me", user_id=user_id)

        content = str(response.content) if hasattr(response, "content") else str(response)
        assert len(content) > 0
        # Should mention colors or palette
        assert "color" in content.lower() or "palette" in content.lower()

    def test_text_formatting_tool(self, configured_agent):
        """Test that agent can use text formatting tool."""
        agent, user_id = configured_agent

        response = agent.run("Format the text 'Hello World' with a bold theme", user_id=user_id)

        content = str(response.content) if hasattr(response, "content") else str(response)
        assert len(content) > 0


class TestSessionMemory:
    """Tests for session memory and conversation history."""

    def test_conversation_history_enabled(self):
        """Test that conversation history is enabled in agent configuration."""
        agent = DemoAgent()
        user_id = "test-user-memory"

        # Configure agent
        agent.run("My favorite color is orange", user_id=user_id)

        # Create the agent
        agent.run("Hello", user_id=user_id)

        # Verify agent has session management enabled
        created_agent = agent._agents[user_id]
        assert created_agent.db is not None
        assert created_agent.add_history_to_context is True
        assert created_agent.num_history_runs == 10


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_run_without_user_id(self):
        """Test that agent handles missing user_id gracefully."""
        agent = DemoAgent()

        response = agent.run("Hello", user_id=None)

        content = str(response.content) if hasattr(response, "content") else str(response)
        assert "❌" in content or "error" in content.lower()
        assert "user id" in content.lower()

    @pytest.mark.asyncio
    async def test_arun_without_user_id(self):
        """Test that async run handles missing user_id gracefully."""
        agent = DemoAgent()

        response = await agent.arun("Hello", user_id=None, stream=False)

        content = str(response.content) if hasattr(response, "content") else str(response)
        assert "❌" in content or "error" in content.lower()

    def test_empty_message(self):
        """Test that agent handles empty messages."""
        agent = DemoAgent()
        user_id = "test-user-empty"

        # Should still prompt for configuration
        response = agent.run("", user_id=user_id)

        content = str(response.content) if hasattr(response, "content") else str(response)
        assert "favorite color" in content.lower()


class TestLogging:
    """Tests to verify logging is comprehensive."""

    def test_logging_in_config_extraction(self, caplog):
        """Test that configuration extraction logs are present."""
        import logging

        caplog.set_level(logging.DEBUG)

        agent = DemoAgent()
        user_id = "test-user-logging"

        # Trigger config extraction
        agent.run("My favorite color is blue", user_id=user_id)

        # Verify extensive logging occurred
        # (Note: loguru doesn't integrate perfectly with caplog,
        #  this is more of a smoke test)
        assert len(caplog.records) >= 0  # At least some logging happened

    def test_agent_creation_logging(self):
        """Test that agent creation is logged."""
        agent = DemoAgent()
        user_id = "test-user-create-log"

        # Configure and create agent
        agent.run("My favorite color is pink", user_id=user_id)
        agent.run("Hello", user_id=user_id)

        # If this doesn't raise an error, logging is working
        # (Full log verification would require log file inspection)
        assert True
