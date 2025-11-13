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

Creating a custom agent involves three main steps:

1. **Create the agent module** - Define agent factory function
2. **Register with custom handler** - Import in `custom_handler.py`
3. **Add to proxy config** - Register model in `proxy_config.yaml`

### Architecture Pattern

AgentLLM agents follow a specific pattern:

```python
# Agent factory function
def create_my_agent(temperature=None, max_tokens=None, **kwargs):
    # Create and configure Agno Agent
    return Agent(...)

# Agent getter function
def get_agent(agent_name="my-agent", temperature=None, max_tokens=None, **kwargs):
    # Route to appropriate factory
    return create_my_agent(temperature, max_tokens, **kwargs)
```

**Why this pattern?**
- `create_*` functions are reusable and testable
- `get_agent()` provides unified interface for custom handler
- Parameters flow through from API requests to agent model

## Simple Agent (No Tools)

Let's create a simple creative writing agent.

### Step 1: Create Agent Module

Create `src/agentllm/agents/writer_agent.py`:

```python
"""Creative writing agent for generating stories and content."""

from pathlib import Path
from typing import Optional
from agno.agent import Agent
from agno.models.google import Gemini
from agno.db.sqlite import SqliteDb

# Use shared database for conversation history
DB_PATH = Path("tmp/agno_sessions.db")
DB_PATH.parent.mkdir(exist_ok=True)
shared_db = SqliteDb(db_file=str(DB_PATH))


def create_writer_agent(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **model_kwargs
) -> Agent:
    """Create a creative writing agent.

    Args:
        temperature: Sampling temperature (0.0-1.0). Default uses model default.
        max_tokens: Maximum tokens to generate. Default uses model default.
        **model_kwargs: Additional parameters to pass to the model.

    Returns:
        Configured Agno Agent instance
    """
    # Configure model parameters
    model_params = {"id": "gemini-2.5-flash"}

    if temperature is not None:
        model_params["temperature"] = temperature
    if max_tokens is not None:
        model_params["max_tokens"] = max_tokens

    # Add any additional model parameters
    model_params.update(model_kwargs)

    return Agent(
        name="writer-agent",
        model=Gemini(**model_params),
        description="Creative writing assistant for stories, articles, and content",
        instructions=[
            "You are a creative writing assistant.",
            "Help users craft engaging stories, articles, and creative content.",
            "Provide constructive feedback on writing.",
            "Suggest plot ideas, character development, and narrative structures.",
            "Adapt your tone and style to match the user's needs.",
        ],
        markdown=True,                   # Enable markdown formatting
        db=shared_db,                    # Shared session database
        add_history_to_context=True,     # Include conversation history
        num_history_runs=10,             # Keep last 10 exchanges
        read_chat_history=True,          # Read history on initialization
    )


def get_agent(
    agent_name: str = "writer-agent",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **model_kwargs
) -> Agent:
    """Get a writer agent instance.

    Args:
        agent_name: Name of the agent to create (must be "writer-agent")
        temperature: Sampling temperature
        max_tokens: Maximum tokens
        **model_kwargs: Additional model parameters

    Returns:
        Agent instance

    Raises:
        KeyError: If agent_name is not recognized
    """
    if agent_name != "writer-agent":
        raise KeyError(f"Agent '{agent_name}' not found.")

    return create_writer_agent(temperature, max_tokens, **model_kwargs)
```

### Step 2: Register with Custom Handler

Edit `src/agentllm/custom_handler.py` and add import:

```python
# Add to imports section
from agentllm.agents import writer_agent

# Update _get_agent_module() function
def _get_agent_module(self, model: str):
    """Get the appropriate agent module based on model name."""
    agent_modules = {
        "agno/release-manager": release_manager,
        "agno/demo-agent": demo_agent,
        "agno/writer-agent": writer_agent,  # Add this line
    }

    agent_module = agent_modules.get(model)
    if agent_module is None:
        raise ValueError(f"Unknown agent model: {model}")
    return agent_module
```

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

Now let's add tools to give agents capabilities.

### Example: Weather Agent with API Tool

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

Create `src/agentllm/agents/weather_agent.py`:

```python
"""Weather agent with API tools."""

import os
from pathlib import Path
from typing import Optional
from agno.agent import Agent
from agno.models.google import Gemini
from agno.db.sqlite import SqliteDb

from agentllm.tools.weather_toolkit import WeatherTools

# Shared database
DB_PATH = Path("tmp/agno_sessions.db")
DB_PATH.parent.mkdir(exist_ok=True)
shared_db = SqliteDb(db_file=str(DB_PATH))


def create_weather_agent(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **model_kwargs
) -> Agent:
    """Create weather agent with API tools."""
    model_params = {"id": "gemini-2.5-flash"}

    if temperature is not None:
        model_params["temperature"] = temperature
    if max_tokens is not None:
        model_params["max_tokens"] = max_tokens

    model_params.update(model_kwargs)

    # Get API key from environment
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        raise ValueError("OPENWEATHER_API_KEY environment variable not set")

    # Create tools
    weather_tools = WeatherTools(api_key=api_key)

    return Agent(
        name="weather-agent",
        model=Gemini(**model_params),
        description="Weather assistant with real-time weather data",
        instructions=[
            "You are a weather assistant.",
            "Use the weather tools to provide current weather and forecasts.",
            "Always specify the city clearly when using tools.",
            "Provide helpful context and recommendations based on weather.",
        ],
        tools=[weather_tools],           # Add tools here
        markdown=True,
        db=shared_db,
        add_history_to_context=True,
        num_history_runs=10,
        read_chat_history=True,
        show_tool_calls=True,            # Show tool usage to user
    )


def get_agent(
    agent_name: str = "weather-agent",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **model_kwargs
) -> Agent:
    """Get weather agent instance."""
    if agent_name != "weather-agent":
        raise KeyError(f"Agent '{agent_name}' not found.")

    return create_weather_agent(temperature, max_tokens, **model_kwargs)
```

Add to `.env.secrets`:
```bash
OPENWEATHER_API_KEY=your_api_key_here
```

Register and configure as before (steps 2-3 from simple agent).

## Agent with Configuration

For agents that need user-specific configuration (OAuth, API tokens), use the toolkit configuration pattern.

### Example: Notion Agent with User Configuration

See `src/agentllm/agents/demo_agent.py` for a complete reference implementation.

Key components:

1. **Configuration class** (extends `BaseToolkitConfig`):

```python
from agentllm.agents.toolkit_configs.base import BaseToolkitConfig

class NotionConfig(BaseToolkitConfig):
    """Notion integration configuration."""

    def is_configured(self, user_id: str) -> bool:
        """Check if user has configured Notion."""
        # Check database for stored token
        pass

    def extract_and_store_config(self, message: str, user_id: str) -> bool:
        """Extract and store Notion API token from message."""
        # Parse message for token, validate, store
        pass

    def get_config_prompt(self) -> str:
        """Return prompt asking user for Notion API token."""
        pass

    def get_toolkit(self, user_id: str):
        """Return configured Notion toolkit."""
        # Get token from database, create toolkit
        pass
```

2. **Wrapper agent class** (like `ReleaseManager` or `DemoAgent`):

```python
class NotionAgent:
    """Wrapper for Notion agent with configuration management."""

    def __init__(self, temperature=None, max_tokens=None, **kwargs):
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model_kwargs = kwargs

        # Register toolkit configurations
        self.toolkit_configs = [
            NotionConfig(is_required=True)
        ]

        # Per-user agent cache
        self._agents = {}

    def run(self, message: str, user_id: str = "default", **kwargs):
        """Run agent with configuration handling."""
        # Check for embedded configuration
        # Prompt if not configured
        # Get/create agent
        # Execute and return response
        pass
```

See [CLAUDE.md - Agent Wrapper Pattern](../../CLAUDE.md#agent-wrapper-pattern) for complete details.

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

Always support parameter pass-through:

```python
def create_my_agent(temperature=None, max_tokens=None, **model_kwargs):
    model_params = {"id": "gemini-2.5-flash"}

    # Add optional parameters
    if temperature is not None:
        model_params["temperature"] = temperature
    if max_tokens is not None:
        model_params["max_tokens"] = max_tokens

    # Pass through any additional parameters
    model_params.update(model_kwargs)

    return Agent(model=Gemini(**model_params), ...)
```

This allows API users to control model behavior:
```bash
curl -d '{
  "model": "agno/my-agent",
  "temperature": 0.3,     # Precise responses
  "max_tokens": 1000,     # Longer responses
  ...
}'
```

### Database and Sessions

Always use the shared database:

```python
from agno.db.sqlite import SqliteDb
from pathlib import Path

DB_PATH = Path("tmp/agno_sessions.db")
DB_PATH.parent.mkdir(exist_ok=True)
shared_db = SqliteDb(db_file=str(DB_PATH))

# In your agent
Agent(
    db=shared_db,
    add_history_to_context=True,
    num_history_runs=10,
)
```

**Benefits:**
- Persistent conversation history
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

- [CONFIGURATION.md](../CONFIGURATION.md) - Configure OAuth and API keys
- [DEVELOPMENT.md](../DEVELOPMENT.md) - Development workflows
- [CLAUDE.md](../../CLAUDE.md) - Deep dive into architecture
- [Demo Agent Source](../../src/agentllm/agents/demo_agent.py) - Complete reference implementation

Happy agent building! 🤖
