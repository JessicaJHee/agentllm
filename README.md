# AgentLLM - Agno Provider for LiteLLM

A custom LiteLLM provider that exposes [Agno](https://github.com/agno-agi/agno) agents through an OpenAI-compatible API, enabling seamless integration with Open WebUI and other OpenAI-compatible clients.

> **Note:** This project uses LiteLLM's official `CustomLLM` extension mechanism with dynamic registration via `custom_provider_map`. No forking or monkey patching required!

## Quick Start

Get the full stack running in under 5 minutes:

**Prerequisites:** [Podman](https://podman.io/) and a [Gemini API key](https://aistudio.google.com/apikey)

```bash
# 1. Clone and navigate
git clone https://github.com/durandom/agentllm
cd agentllm

# 2. Configure environment
cp .env.secrets.template .env.secrets
# Edit .env.secrets and add your GEMINI_API_KEY (get from https://aistudio.google.com/apikey)

# 3. Start everything (easiest way!)
podman compose up
```

**Access Open WebUI:** <http://localhost:3000>

**Available Agents:**
- `agno/release-manager` - RHDH release management assistant
- `agno/sprint-reviewer` - Sprint review assistant
- `agno/demo-agent` - Example agent with color tools

> **Note:** Agent data (session history, credentials) is stored in the `tmp/` directory, which persists across restarts.

## Architecture

```mermaid
flowchart LR;
    Client-->LiteLLM_Proxy;
    LiteLLM_Proxy-->Agno_Provider;
    Agno_Provider-->Agno_Agent;
    Agno_Agent-->LLM_APIs;
```

**Components:**
- **LiteLLM Proxy**: OpenAI-compatible API gateway with authentication
- **Agno Provider**: Custom LiteLLM handler (`litellm.CustomLLM`) for Agno agents
- **Agno Agents**: Intelligent agents with tools (Google Drive, Jira, etc.)
- **Gemini API**: Underlying LLM (Google Gemini 2.5 Flash)

The provider uses LiteLLM's official `custom_provider_map` for dynamic registration:

```yaml
litellm_settings:
  custom_provider_map:
    - provider: "agno"
      custom_handler: custom_handler.agno_handler
```

See [CLAUDE.md](CLAUDE.md) for detailed architecture documentation.

## Development

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager ([install](https://docs.astral.sh/uv/getting-started/installation/): `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- [nox](https://nox.thea.codes/) task automation ([install](https://nox.thea.codes/en/stable/tutorial.html#installation): `uv tool install nox`)
- [Podman](https://podman.io/) ([install](https://podman.io/getting-started/installation))
- Google Gemini API key ([get here](https://aistudio.google.com/apikey))

### Development Modes

**Choose based on your workflow:**

| Mode | Command | Use When | Proxy | OpenWebUI |
|------|---------|----------|-------|-----------|
| **Quick Start** ⭐ | `podman compose up` | **Easiest way** - just running the system | Container | Container |
| **Full Container** | `nox -s dev` or `nox -s dev_build` | Need to rebuild after code changes | Container | Container |
| **Development** | Terminal 1: `nox -s proxy`<br>Terminal 2: `nox -s dev_local_proxy` | Modifying agent code (hot reload) | Local (hot reload) | Container |

**Notes:**
- `podman compose up` is the simplest way to get started - no Python/uv/nox required!
- Use `nox -s dev` for quick starts (reuses existing images), or `nox -s dev_build` when you need to rebuild after code changes
- Agent data is stored in `tmp/` directory and persists across restarts

**Port reference:**
- Open WebUI: <http://localhost:3000> (external) → container port 8080 (internal)
- LiteLLM Proxy: <http://localhost:8890>

### Common Commands

```bash
# Testing
nox -s test                                    # Run unit tests
nox -s integration                             # Run integration tests (requires running proxy)
uv run pytest tests/test_custom_handler.py -v  # Run specific test

# Development
podman compose up                              # Easiest: start everything (Quick Start)
nox -s proxy                                   # Start LiteLLM proxy locally
nox -s dev                                     # Start full containerized stack (no rebuild)
nox -s dev_build                               # Build and start (forces rebuild)
nox -s dev_logs                                # View container logs
nox -s dev_stop                                # Stop containers (preserve tmp/ data)
nox -s dev_clean                               # Clean everything (containers + tmp/ directory)

# Code quality
nox -s format                                  # Format code
make lint                                      # Run linting
```

### Testing the Proxy

```bash
# Start proxy
nox -s proxy

# Make a request
curl -X POST http://localhost:8890/v1/chat/completions \
  -H "Authorization: Bearer sk-agno-test-key-12345" \
  -H "Content-Type: application/json" \
  -H "X-OpenWebUI-User-Id: test-user" \
  -d '{
    "model": "agno/demo-agent",
    "messages": [{"role": "user", "content": "Hey"}]
  }'
```

## Available Models

**Agno Agents** (powered by Gemini 2.5 Flash):
- `agno/release-manager` - RHDH release management assistant (Google Drive, Jira integration)
- `agno/sprint-reviewer` - Sprint review assistant (Google Drive, Jira integration)
- `agno/demo-agent` - Example agent with color tools (educational reference)

**Direct Gemini Models:**
- `gemini-2.5-pro` - Most capable model
- `gemini-2.5-flash` - Fast and efficient (used by Agno agents)

List models from running proxy:
```bash
curl -X GET http://localhost:8890/v1/models \
  -H "Authorization: Bearer sk-agno-test-key-12345"
```

> **Note:** All models require `GEMINI_API_KEY` in your `.env.secrets` file.

## Adding New Agents

See [docs/agents/creating-agents.md](docs/agents/creating-agents.md) for a complete guide. AgentLLM now supports a **plugin-based architecture** with automatic agent discovery.

### Quick Start (Plugin System - Recommended)

1. **Create configurator** in `src/agentllm/agents/my_agent_configurator.py`:

```python
from agentllm.agents.base import AgentConfigurator, BaseToolkitConfig

class MyAgentConfigurator(AgentConfigurator):
    def _initialize_toolkit_configs(self) -> list[BaseToolkitConfig]:
        return []  # Add toolkit configs here

    def _build_agent_instructions(self) -> list[str]:
        return ["You are my agent.", "Your purpose is..."]

    def _get_agent_name(self) -> str:
        return "my-agent"

    def _get_agent_description(self) -> str:
        return "My agent description"
```

2. **Create agent wrapper** in `src/agentllm/agents/my_agent.py`:

```python
from agentllm.agents.base import BaseAgentWrapper, AgentFactory
from .my_agent_configurator import MyAgentConfigurator

class MyAgent(BaseAgentWrapper):
    def _create_configurator(self, user_id, session_id, shared_db, **kwargs):
        return MyAgentConfigurator(
            user_id=user_id,
            session_id=session_id,
            shared_db=shared_db,
            **kwargs
        )

class MyAgentFactory(AgentFactory):
    @staticmethod
    def create_agent(shared_db, token_storage, user_id, session_id=None,
                    temperature=None, max_tokens=None, **kwargs):
        return MyAgent(shared_db=shared_db, user_id=user_id,
                      session_id=session_id, **kwargs)

    @staticmethod
    def get_metadata():
        return {
            "name": "my-agent",
            "description": "My agent description",
            "mode": "chat",
        }
```

3. **Register in `pyproject.toml`**:

```toml
[project.entry-points."agentllm.agents"]
my-agent = "agentllm.agents.my_agent:MyAgentFactory"
```

4. **Add to proxy config** in `proxy_config.yaml`:

```yaml
- model_name: agno/my-agent
  litellm_params:
    model: agno/my-agent
    custom_llm_provider: agno
```

5. **Restart proxy**: `nox -s proxy` - Your agent will be auto-discovered!

## Configuration

### Environment Variables

Required:
- `GEMINI_API_KEY` - Google Gemini API key ([get here](https://aistudio.google.com/apikey))
- `LITELLM_MASTER_KEY` - Proxy API key (default: `sk-agno-test-key-12345`)

Optional:
- `OPENAI_API_BASE_URL` - LiteLLM proxy URL for Open WebUI
  - Development: `http://host.docker.internal:8890/v1` (default)
  - Production: `http://litellm-proxy:8890/v1`
- `GDRIVE_CLIENT_ID`, `GDRIVE_CLIENT_SECRET` - For Google Drive integration
- `RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL` - Extended system prompt URL

See `.env.secrets.template` for all available configuration options.

### Proxy Configuration

Edit `proxy_config.yaml` to:
- Add/remove models (Agno agents, Gemini, or other LLM providers)
- Configure authentication
- Adjust logging and server settings

### Data Storage

AgentLLM stores all agent data in the `tmp/` directory:

```
tmp/
├── agno_sessions.db        # Session history and conversation context
├── agno_credentials.db     # User credentials (OAuth tokens, API keys)
└── agno_handler.log        # Application logs
```

**Key Points:**
- Data persists across container restarts (volume-mounted in `compose.yaml`)
- Delete `tmp/` to reset all agents and clear credentials
- Session history is per-user and per-agent
- Credentials are encrypted and stored securely per-user

## Key Features

### LiteLLM Custom Provider

The Agno provider extends `litellm.CustomLLM` and implements:

- `completion()` - Synchronous completions with full agent execution
- `streaming()` - Synchronous streaming (GenericStreamingChunk format)
- `acompletion()` - Async completions using `agent.arun()`
- `astreaming()` - True real-time streaming with `agent.arun(stream=True)` ⚡

**Key Benefits:**
- No LiteLLM modifications required
- Parameter pass-through (`temperature`, `max_tokens` → agent model)
- Conversation context preserved in agent sessions
- Per-user agent isolation

### Plugin-Based Architecture

AgentLLM uses a **plugin system** with automatic agent discovery:

- **AgentFactory**: Entry point registration via `pyproject.toml`
- **AgentConfigurator**: Separates configuration management from execution
- **BaseAgentWrapper**: Provides common execution interface
- **AgentRegistry**: Automatically discovers and registers agents at runtime

**Benefits:**
- Agents can be distributed as separate packages
- No manual imports needed - automatic discovery
- Clean separation between configuration and execution
- Metadata system for agent capabilities

### Streaming Support

LiteLLM's `CustomLLM` requires **GenericStreamingChunk format**:

```python
{
    "text": "content here",           # Use "text", not "content"
    "finish_reason": "stop" or None,
    "index": 0,
    "is_finished": True or False,
    "tool_use": None,
    "usage": {...}
}
```

**Async streaming** provides true real-time token-by-token streaming using Agno's native `async for` with `agent.arun(stream=True)`.

## Project Structure

```
agentllm/
├── src/agentllm/
│   ├── custom_handler.py              # LiteLLM CustomLLM implementation
│   ├── proxy_config.yaml              # LiteLLM proxy configuration
│   ├── agents/
│   │   ├── base/                      # Plugin system base classes
│   │   │   ├── factory.py             #   AgentFactory ABC
│   │   │   ├── registry.py            #   AgentRegistry (auto-discovery)
│   │   │   ├── configurator.py        #   AgentConfigurator (config mgmt)
│   │   │   ├── wrapper.py             #   BaseAgentWrapper (execution)
│   │   │   └── toolkit_config.py      #   BaseToolkitConfig (re-export)
│   │   ├── release_manager.py         # Production agent wrapper
│   │   ├── release_manager_configurator.py  # Release manager config
│   │   ├── demo_agent.py              # Demo agent (reference impl)
│   │   ├── demo_agent_configurator.py # Demo agent config
│   │   ├── sprint_reviewer.py         # SprintReviewer wrapper class
│   │   ├── sprint_reviewer_configurator.py  # SprintReviewer config
│   │   └── toolkit_configs/
│   │       ├── gdrive_config.py       # Google Drive OAuth
│   │       ├── jira_config.py         # Jira API token
│   │       └── favorite_color_config.py  # Demo config
│   ├── tools/
│   │   ├── gdrive_toolkit.py          # Google Drive tools
│   │   ├── jira_toolkit.py            # Jira tools
│   │   └── color_toolkit.py           # Demo color tools
│   └── db/
│       └── token_storage.py           # SQLite credential storage
├── tests/
│   ├── test_custom_handler.py         # Provider tests
│   ├── test_release_manager.py        # ReleaseManager tests
│   ├── test_sprint_reviewer.py        # SprintReviewer tests
│   └── test_demo_agent.py             # Demo agent tests
├── docs/
│   ├── agents/
│   │   ├── creating-agents.md         # Complete agent creation guide
│   └── templates/                     # Documentation templates
├── noxfile.py                         # Task automation
├── proxy_config.yaml                  # Proxy config (symlink to src/)
├── AGENTS.md                          # Architecture patterns & developer guide
└── CLAUDE.md                          # Reference to AGENTS.md
```

## Documentation

- **[Creating Agents](docs/agents/creating-agents.md)** - Complete guide to building custom agents with tools and configuration
- **[AGENTS.md](AGENTS.md)** - Architecture patterns, plugin system, and developer guide for contributors
- **[Release Manager](docs/agents/release_manager.md)** - RHDH release management assistant

## Troubleshooting

### Tests Fail with "No module named 'agentllm'"

```bash
uv pip install -e .
```

### Agent Fails to Initialize

Ensure `GEMINI_API_KEY` is set in `.env.secrets`. Get your key from [Google AI Studio](https://aistudio.google.com/apikey).

### Proxy Won't Start

Check that port 8890 is available:

```bash
lsof -i :8890
```

### Can't Access Open WebUI

- Verify container is running: `podman ps`
- Check port mapping: Should see `0.0.0.0:3000->8080/tcp`
- Try http://localhost:3000 (external port, not 8080)
- Check container logs: `nox -s dev_logs`

### Reset Agent Data or Clear Credentials

To reset all agent sessions and credentials:

```bash
# Stop containers first
podman compose down
# or
nox -s dev_stop

# Remove agent data
rm -rf tmp/

# Restart
podman compose up
```

This clears:
- All conversation history
- Stored OAuth tokens and API keys
- Agent session state

## Contributing

1. Write tests for new features (TDD workflow)
2. Run tests: `nox -s test`
3. Format code: `nox -s format`
4. Run linting: `make lint`
5. Update documentation

## License

GPL-3.0-only

## References

- [Agno Framework](https://github.com/agno-agi/agno)
- [LiteLLM](https://github.com/BerriAI/litellm)
- [LiteLLM CustomLLM Docs](https://docs.litellm.ai/docs/providers/custom_llm_server)
- [Open WebUI](https://github.com/open-webui/open-webui)
