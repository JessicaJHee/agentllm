# Creating Custom Agents

This guide walks you through creating custom Agno agents for AgentLLM, from simple agents to complex ones with tools and configuration.

## Table of Contents

- [Overview](#overview)
- [Simple Agent (No Tools)](#simple-agent-no-tools)
- [Agent with Tools](#agent-with-tools)
- [Agent with Configuration](#agent-with-configuration)
- [Testing Your Agent](#testing-your-agent)
- [Best Practices](#best-practices)

## Overview

Creating a custom agent involves four main steps:

1. **Create the agent class** - Extend `BaseAgentWrapper` and implement abstract methods
2. **Register with custom handler** - Import class and add instantiation logic in `custom_handler.py`
3. **Add to proxy config** - Register model in `proxy_config.yaml`
4. **Test the agent** - Verify via curl or OpenWebUI

### Architecture Pattern

AgentLLM agents follow a **class-based wrapper pattern** that extends `BaseAgentWrapper`:

```python
from agentllm.agents.base_agent import BaseAgentWrapper
from agentllm.agents.toolkit_configs.base import BaseToolkitConfig
from agno.db.sqlite import SqliteDb
from agentllm.db import TokenStorage

class MyAgent(BaseAgentWrapper):
    """My custom agent implementation."""

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
        # Call parent constructor (handles common setup)
        super().__init__(
            shared_db=shared_db,
            user_id=user_id,
            session_id=session_id,
            temperature=temperature,
            max_tokens=max_tokens,
            **model_kwargs,
        )

    # Implement 4 required abstract methods:

    def _initialize_toolkit_configs(self) -> list[BaseToolkitConfig]:
        """Return list of toolkit configurations (or empty list)."""
        return []  # No toolkits, or [MyToolkitConfig(), ...]

    def _get_agent_name(self) -> str:
        """Return agent identifier (e.g., 'my-agent')."""
        return "my-agent"

    def _get_agent_description(self) -> str:
        """Return agent description for users."""
        return "My custom agent for ..."

    def _build_agent_instructions(self, user_id: str) -> list[str]:
        """Return agent instructions/system prompt."""
        return [
            "You are my custom agent.",
            "Your purpose is to...",
        ]
```

**Why this pattern?**
- **Separation of concerns**: Base class handles configuration management, streaming, caching
- **Per-user isolation**: Each wrapper instance is tied to a specific user+session
- **Dependency injection**: Database and token storage passed explicitly (testable)
- **Reusable logic**: All agents share common functionality from `BaseAgentWrapper`
- **Type safety**: Abstract methods enforce implementation contract

## Simple Agent (No Tools)

Let's create a simple creative writing agent with no external tools or configuration requirements.

### Step 1: Create Agent Class

Create `src/agentllm/agents/writer_agent.py`:

```python
"""Creative writing agent for generating stories and content."""

from agentllm.agents.base_agent import BaseAgentWrapper
from agentllm.agents.toolkit_configs.base import BaseToolkitConfig
from agno.db.sqlite import SqliteDb
from agentllm.db import TokenStorage


class WriterAgent(BaseAgentWrapper):
    """Creative writing agent with no tools or required configuration."""

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
        """
        Initialize the Writer Agent.

        Args:
            shared_db: Shared database instance for session management
            token_storage: Token storage instance for credentials
            user_id: User identifier
            session_id: Session identifier (optional)
            temperature: Model temperature (0.0-2.0)
            max_tokens: Maximum tokens in response
            **model_kwargs: Additional model parameters
        """
        # Call parent constructor
        super().__init__(
            shared_db=shared_db,
            user_id=user_id,
            session_id=session_id,
            temperature=temperature,
            max_tokens=max_tokens,
            **model_kwargs,
        )

    def _initialize_toolkit_configs(self) -> list[BaseToolkitConfig]:
        """No toolkits needed for this simple agent."""
        return []

    def _get_agent_name(self) -> str:
        """Return agent name."""
        return "writer-agent"

    def _get_agent_description(self) -> str:
        """Return agent description."""
        return "Creative writing assistant for stories, articles, and content"

    def _build_agent_instructions(self, user_id: str) -> list[str]:
        """Return agent instructions."""
        return [
            "You are a creative writing assistant.",
            "Help users craft engaging stories, articles, and creative content.",
            "Provide constructive feedback on writing.",
            "Suggest plot ideas, character development, and narrative structures.",
            "Adapt your tone and style to match the user's needs.",
        ]
```

**Key Points:**
- Extends `BaseAgentWrapper` to inherit common functionality
- No toolkits (returns empty list from `_initialize_toolkit_configs()`)
- Simple instructions for creative writing tasks
- All parameter handling is done by base class

### Step 2: Register with Custom Handler

Edit `src/agentllm/custom_handler.py`:

**Add import at the top:**
```python
from agentllm.agents.writer_agent import WriterAgent
```

**Add instantiation logic in `_get_agent_instance()` method:**
```python
def _get_agent_instance(self, model: str, ...) -> BaseAgentWrapper:
    """Get or create agent wrapper instance."""

    # Extract agent name and parameters...

    # Instantiate appropriate agent class
    if agent_name == "release-manager":
        agent = ReleaseManager(
            shared_db=shared_db,
            token_storage=token_storage,
            user_id=effective_user_id,
            session_id=session_id,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    elif agent_name == "demo-agent":
        agent = DemoAgent(
            shared_db=shared_db,
            token_storage=token_storage,
            user_id=effective_user_id,
            session_id=session_id,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    elif agent_name == "writer-agent":  # Add this block
        agent = WriterAgent(
            shared_db=shared_db,
            token_storage=token_storage,
            user_id=effective_user_id,
            session_id=session_id,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:
        error_msg = f"Agent '{agent_name}' not found. Available agents: 'release-manager', 'demo-agent', 'writer-agent'"
        raise ValueError(error_msg)

    return agent
```

**Key Points:**
- Import the class directly (not as a module)
- Instantiate with all required parameters (dependency injection)
- The wrapper instance is cached by custom_handler per (user_id, session_id, model, temperature, max_tokens)

### Step 3: Add to Proxy Config

Edit `proxy_config.yaml` and add model entry:

```yaml
model_list:
  # Existing models...

  # Creative Writing Agent
  - model_name: agno/writer-agent
    litellm_params:
      model: agno/writer-agent
      custom_llm_provider: agno
```

### Step 4: Test the Agent

```bash
# Restart proxy
nox -s dev_stop
nox -s dev_build

# Test with curl
curl -X POST http://localhost:8890/v1/chat/completions \
  -H "Authorization: Bearer sk-agno-test-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "agno/writer-agent",
    "messages": [
      {"role": "user", "content": "Help me write a short story about a robot learning to paint"}
    ]
  }'
```

Or test via Open WebUI:
1. Open http://localhost:3000
2. Select `agno/writer-agent`
3. Start chatting!

## Agent with Tools

Now let's add tools to give agents capabilities. Tools in AgentLLM are organized into `Toolkit` classes.

### Example: Weather Agent with API Tool

**Step 1: Create the Toolkit**

Create `src/agentllm/tools/weather_toolkit.py`:

```python
"""Weather tools for fetching weather data."""

from agno.toolkit import Toolkit
from agno.tools import tool


class WeatherTools(Toolkit):
    """Tools for weather information."""

    def __init__(self, api_key: str):
        """Initialize weather tools.

        Args:
            api_key: OpenWeatherMap API key
        """
        super().__init__(name="weather_tools")
        self.api_key = api_key
        self.register(self.get_current_weather)
        self.register(self.get_forecast)

    @tool
    def get_current_weather(self, city: str) -> str:
        """Get current weather for a city.

        Args:
            city: Name of the city

        Returns:
            Current weather description
        """
        import requests

        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={self.api_key}&units=metric"

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            temp = data["main"]["temp"]
            description = data["weather"][0]["description"]

            return f"Current weather in {city}: {description}, {temp}°C"
        except Exception as e:
            return f"Error fetching weather: {str(e)}"

    @tool
    def get_forecast(self, city: str, days: int = 3) -> str:
        """Get weather forecast for a city.

        Args:
            city: Name of the city
            days: Number of days to forecast (1-5)

        Returns:
            Weather forecast
        """
        import requests

        url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={self.api_key}&units=metric"

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            # Process forecast data (simplified)
            forecasts = data["list"][:days * 8]  # 8 forecasts per day

            result = f"Weather forecast for {city}:\n"
            for forecast in forecasts[::8]:  # One per day
                date = forecast["dt_txt"].split()[0]
                temp = forecast["main"]["temp"]
                desc = forecast["weather"][0]["description"]
                result += f"- {date}: {desc}, {temp}°C\n"

            return result
        except Exception as e:
            return f"Error fetching forecast: {str(e)}"
```

**Step 2: Create Agent Class with Tools**

Create `src/agentllm/agents/weather_agent.py`:

```python
"""Weather agent with API tools."""

import os
from agentllm.agents.base_agent import BaseAgentWrapper
from agentllm.agents.toolkit_configs.base import BaseToolkitConfig
from agno.db.sqlite import SqliteDb
from agentllm.db import TokenStorage
from agentllm.tools.weather_toolkit import WeatherTools


class WeatherAgent(BaseAgentWrapper):
    """Weather agent with API tools."""

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
        """Initialize Weather Agent."""
        # Get API key from environment
        self.api_key = os.getenv("OPENWEATHER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENWEATHER_API_KEY environment variable not set")

        # Call parent constructor
        super().__init__(
            shared_db=shared_db,
            user_id=user_id,
            session_id=session_id,
            temperature=temperature,
            max_tokens=max_tokens,
            **model_kwargs,
        )

    def _initialize_toolkit_configs(self) -> list[BaseToolkitConfig]:
        """No user configuration needed - using shared API key."""
        return []

    def _get_agent_name(self) -> str:
        """Return agent name."""
        return "weather-agent"

    def _get_agent_description(self) -> str:
        """Return agent description."""
        return "Weather assistant with real-time weather data"

    def _build_agent_instructions(self, user_id: str) -> list[str]:
        """Return agent instructions."""
        return [
            "You are a weather assistant.",
            "Use the weather tools to provide current weather and forecasts.",
            "Always specify the city clearly when using tools.",
            "Provide helpful context and recommendations based on weather.",
        ]

    def _collect_toolkits(self, user_id: str) -> list:
        """Return tools for this agent (shared API key, no per-user config)."""
        return [WeatherTools(api_key=self.api_key)]
```

**Step 3: Configure Environment**

Add to `.env.secrets`:
```bash
OPENWEATHER_API_KEY=your_api_key_here
```

**Step 4: Register and Test**

Register in `custom_handler.py` as shown in the simple agent example, then test via curl or OpenWebUI.

**Key Points:**
- Tools are created by overriding `_collect_toolkits()` method (called by base class when building agent)
- For shared services (no per-user credentials): Override `_collect_toolkits()` to return toolkit instances directly
- For per-user credentials (OAuth, API tokens): Use toolkit configs (see next section)

## Agent with Configuration

For agents that need user-specific configuration (OAuth tokens, API keys), use **toolkit configurations**. Toolkit configs handle extracting, storing, and retrieving per-user credentials.

### Architecture

Toolkit configurations enable agents to:
1. Prompt users for credentials when needed
2. Extract credentials from natural language messages
3. Store credentials securely per user
4. Provide configured toolkits to the agent

### Example: DemoAgent with Required Configuration

The **Demo Agent** (`src/agentllm/agents/demo_agent.py`) is the reference implementation. It demonstrates:

- **Required configuration**: `FavoriteColorConfig` (user must configure before using agent)
- **Simple toolkit**: `ColorTools` (no external APIs)
- **Configuration extraction**: Recognizes patterns like "my favorite color is blue"
- **Per-user isolation**: Each user has their own configuration

**Key Code Patterns:**

```python
class DemoAgent(BaseAgentWrapper):
    """Agent with required configuration."""

    def __init__(self, shared_db, token_storage, user_id, session_id=None, ...):
        # Store token_storage for toolkit config
        self._token_storage = token_storage
        super().__init__(...)

    def _initialize_toolkit_configs(self) -> list[BaseToolkitConfig]:
        """Register toolkit configurations."""
        return [
            FavoriteColorConfig(token_storage=self._token_storage),  # Required config
        ]

    # ... other abstract methods ...
```

**How Configuration Works:**

1. **First message**: Agent checks if `FavoriteColorConfig.is_configured(user_id)` returns True
2. **If not configured**: Agent returns prompt from `get_config_prompt()`
3. **User sends config**: "My favorite color is blue"
4. **Extraction**: `extract_and_store_config()` extracts "blue" and stores it
5. **Toolkit creation**: `get_toolkit(user_id)` returns `ColorTools` configured with "blue"
6. **Agent continues**: Now that config is complete, agent can assist user

### Creating Your Own Toolkit Config

See these reference implementations:

- **Simple example**: `src/agentllm/agents/toolkit_configs/favorite_color_config.py` - In-memory configuration
- **OAuth example**: `src/agentllm/agents/toolkit_configs/gdrive_config.py` - Google Drive OAuth flow
- **API token example**: `src/agentllm/agents/toolkit_configs/jira_config.py` - Jira API token storage
- **Base class**: `src/agentllm/agents/toolkit_configs/base.py` - Abstract methods you must implement

Required methods to implement:
- `is_configured(user_id)` - Check if user has provided credentials
- `extract_and_store_config(message, user_id)` - Extract and save credentials from message
- `get_config_prompt()` - Return prompt requesting credentials
- `get_toolkit(user_id)` - Return configured toolkit instance
- `check_authorization_request(message)` - Detect if user is attempting to authorize

## Testing Your Agent

### Unit Tests

Create `tests/test_my_agent.py`:

```python
"""Tests for My Agent."""

import pytest
from agentllm.agents import my_agent


def test_agent_creation():
    """Test basic agent instantiation."""
    agent = my_agent.create_my_agent()
    assert agent.name == "my-agent"
    assert agent.description is not None


def test_agent_with_temperature():
    """Test temperature parameter."""
    agent = my_agent.create_my_agent(temperature=0.7)
    assert agent.model.temperature == 0.7


@pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="Requires GEMINI_API_KEY"
)
def test_agent_execution():
    """Test actual agent execution."""
    agent = my_agent.create_my_agent()
    response = agent.run("Hello!")
    assert response.content is not None
```

Run tests:
```bash
nox -s test
```

### Integration Tests

Test via proxy:

```python
def test_agent_via_proxy():
    """Test agent through LiteLLM proxy."""
    import requests

    response = requests.post(
        "http://localhost:8890/v1/chat/completions",
        headers={
            "Authorization": "Bearer sk-agno-test-key-12345",
            "Content-Type": "application/json"
        },
        json={
            "model": "agno/my-agent",
            "messages": [{"role": "user", "content": "Test message"}]
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "choices" in data
```

### Manual Testing

```bash
# Start proxy
nox -s proxy

# Test with curl
curl -X POST http://localhost:8890/v1/chat/completions \
  -H "Authorization: Bearer sk-agno-test-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "agno/my-agent",
    "messages": [{"role": "user", "content": "Hello!"}],
    "temperature": 0.7,
    "max_tokens": 500
  }'
```

## Best Practices

### Agent Design

1. **Clear purpose**: Each agent should have a well-defined role
2. **Focused tools**: Only include tools relevant to the agent's purpose
3. **Good instructions**: Be specific about behavior and capabilities
4. **Conversation memory**: Use `add_history_to_context=True` for coherent conversations

### Instructions

Good instructions are:
- **Specific**: "Provide code examples" not "be helpful"
- **Actionable**: "Always validate input" not "be careful"
- **Concise**: 3-5 clear directives

Example:
```python
instructions=[
    "You are a Python code review assistant.",
    "Identify bugs, security issues, and code smells.",
    "Suggest specific improvements with code examples.",
    "Explain the reasoning behind each recommendation.",
    "Focus on clarity, efficiency, and maintainability.",
]
```

### Parameter Handling

`BaseAgentWrapper` automatically handles parameter pass-through. Parameters from the API request (temperature, max_tokens) are:

1. Passed to your agent wrapper's `__init__()`
2. Stored by base class in `self._temperature`, `self._max_tokens`, `self._model_kwargs`
3. Automatically applied when creating the Agno Agent instance

**Your responsibility:** Just pass them to `super().__init__()`:

```python
class MyAgent(BaseAgentWrapper):
    def __init__(self, shared_db, token_storage, user_id, session_id=None,
                 temperature=None, max_tokens=None, **model_kwargs):
        # Just pass to parent - it handles everything
        super().__init__(
            shared_db=shared_db,
            user_id=user_id,
            session_id=session_id,
            temperature=temperature,
            max_tokens=max_tokens,
            **model_kwargs,
        )
```

**API usage example:**
```bash
curl -d '{
  "model": "agno/my-agent",
  "temperature": 0.3,     # Precise responses
  "max_tokens": 1000,     # Longer responses
  ...
}'
```

### Database and Sessions

`BaseAgentWrapper` requires `shared_db` via dependency injection:

```python
class MyAgent(BaseAgentWrapper):
    def __init__(self, shared_db: SqliteDb, ...):
        super().__init__(shared_db=shared_db, ...)
```

The `shared_db` is created and passed by `custom_handler.py`:
```python
# In custom_handler.py
DB_PATH = Path("tmp/agno_sessions.db")
shared_db = SqliteDb(db_file=str(DB_PATH))

agent = MyAgent(shared_db=shared_db, ...)  # Injected here
```

**Benefits of this pattern:**
- No need to manage database in your agent code
- Testable (can pass mock database)
- Persistent conversation history across sessions
- Multi-turn conversations work correctly
- Sessions survive proxy restarts

### Security

1. **Validate environment variables:**
   ```python
   api_key = os.getenv("MY_API_KEY")
   if not api_key:
       raise ValueError("MY_API_KEY not set")
   ```

2. **Never log sensitive data:**
   ```python
   # Bad
   print(f"Using API key: {api_key}")

   # Good
   print("API key configured")
   ```

3. **Use per-user credentials** when possible (see toolkit config pattern)

### Performance

1. **Cache expensive resources:**
   ```python
   class MyAgent:
       def __init__(self):
           self._agents = {}  # Cache agents per user
   ```

2. **Lazy initialization:**
   ```python
   @property
   def expensive_resource(self):
       if not hasattr(self, "_resource"):
           self._resource = create_expensive_thing()
       return self._resource
   ```

## Example Agents

Study these reference implementations:

- **Simple agent**: See `writer-agent` example above
- **Agent with tools**: `src/agentllm/agents/demo_agent.py` (lines 1-588)
- **Agent with configuration**: `src/agentllm/agents/release_manager.py` (lines 1-698)
- **Toolkit config**: `src/agentllm/agents/toolkit_configs/favorite_color_config.py`

## Troubleshooting

### Agent Not Found

**Error:** `Unknown agent model: agno/my-agent`

**Solution:**
1. Check import in `custom_handler.py`
2. Verify entry in `_get_agent_module()` dictionary
3. Restart proxy: `nox -s dev_stop && nox -s proxy`

### Tools Not Working

**Issue:** Agent doesn't use tools

**Checklist:**
1. Tools properly registered: `toolkit.register(self.my_tool)`
2. Tools added to agent: `Agent(tools=[my_toolkit], ...)`
3. Tool has `@tool` decorator
4. Tool has proper docstring (agent uses this to understand when to call it)

### Import Errors

**Error:** `ModuleNotFoundError: No module named 'agentllm'`

**Solution:**
```bash
uv pip install -e .
```

## Next Steps

- **[Demo Agent Source](../../src/agentllm/agents/demo_agent.py)** - Complete reference implementation with extensive comments
- **[CLAUDE.md](../../CLAUDE.md)** - Deep dive into architecture and design decisions
- **[.env.secrets.template](../../.env.secrets.template)** - All available configuration options

Happy agent building! 🤖
