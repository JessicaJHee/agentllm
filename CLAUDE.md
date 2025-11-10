# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AgentLLM is a LiteLLM custom provider that exposes Agno agents through an OpenAI-compatible API. It enables seamless integration with Open WebUI and other OpenAI-compatible clients using LiteLLM's official `CustomLLM` extension mechanism.

**Architecture Flow:**

```
[Client] -> [LiteLLM Proxy :8890] -> [Agno Provider] -> [Agno Agent] -> [Gemini API]
```

## Development Commands

### Testing

```bash
# Run unit tests
nox -s test

# Run integration tests (requires running proxy)
nox -s integration

# Run specific test
uv run pytest tests/test_custom_handler.py::TestAgnoCustomLLM -v

# Run specific test file
uv run pytest tests/test_release_manager.py -v
```

### Running the Proxy

```bash
# Start LiteLLM proxy locally
nox -s proxy

# Or directly with uv
uv run litellm --config proxy_config.yaml --port 8890
```

## Development Modes

The project supports two development modes to accommodate different workflows:

### Development Mode (Recommended for Day-to-Day Work)

**Use case:** Fast iteration on proxy/agent code with live debugging

Run the LiteLLM proxy locally and Open WebUI in a container:

```bash
# Terminal 1: Start local proxy with hot reload
nox -s proxy

# Terminal 2: Start Open WebUI (connects to local proxy)
nox -s dev_local_proxy
```

**How it works:**

- `LITELLM_PROXY_URL` in `.env` is set to `http://host.docker.internal:8890/v1`
- Open WebUI (containerized) connects to proxy on host machine
- Works on all platforms (Mac, Linux, Windows) via `extra_hosts` configuration
- Enables fast iteration: edit code → proxy reloads → test immediately

**Advantages:**

- Instant code reloading for proxy changes
- Easy debugging with local debuggers
- Direct log access in terminal
- Lower resource usage (one less container)

### Production Mode (Full Container Stack)

**Use case:** Testing the complete containerized setup or when not modifying proxy code

Run both services in containers:

```bash
# Start both services (foreground)
nox -s dev_full

# Or in background
nox -s dev_full -- -d
```

**How it works:**

- Overrides `LITELLM_PROXY_URL` to `http://litellm-proxy:8890/v1`
- Both services run in Docker network
- Matches production deployment architecture

**Advantages:**

- Production-like environment
- Tests full Docker setup
- Easier for non-Python developers

### Common Docker Commands

```bash
# View logs from containers
nox -s dev-logs                    # All services
nox -s dev-logs -- litellm-proxy   # Specific service

# Stop containers (preserves data)
nox -s dev-stop

# Clean everything (including volumes)
nox -s dev-clean

# Legacy command (still works, starts both services)
nox -s dev
```

### Switching Between Modes

The mode is controlled by the `LITELLM_PROXY_URL` environment variable in `.env`:

```bash
# Development mode (local proxy)
LITELLM_PROXY_URL=http://host.docker.internal:8890/v1

# Production mode (both containerized) - used as default by dev-full
LITELLM_PROXY_URL=http://litellm-proxy:8890/v1
```

**No manual configuration needed** - just use the appropriate `nox` command:

- `nox -s dev_local_proxy` - Uses value from `.env` (development mode)
- `nox -s dev_full` - Automatically overrides to container mode

### Code Quality

```bash
# Run linting
make lint

# Format code
nox -s format
```

### Making Test Requests

```bash
# Test proxy health
nox -s hello
```

## Core Architecture

### LiteLLM Custom Provider Integration

The project uses LiteLLM's **official CustomLLM extension mechanism** with dynamic registration via `custom_provider_map` in `proxy_config.yaml`:

```yaml
litellm_settings:
  custom_provider_map:
    - provider: "agno"
      custom_handler: custom_handler.agno_handler  # Relative to config location
```

**Key Implementation:** `src/agentllm/custom_handler.py`

- Extends `litellm.CustomLLM` base class
- Implements: `completion()`, `streaming()`, `acompletion()`, `astreaming()`
- Manages agent caching per (agent_name, temperature, max_tokens, user_id)
- Extracts session/user context from OpenWebUI headers and metadata

#### Custom Handler Path Resolution Pattern

LiteLLM loads custom handlers using **file-based resolution** relative to the config file location, not Python module imports. This requires a specific project structure:

**File Layout:**

```
project_root/
├── proxy_config.yaml          # Config at root (required by LiteLLM)
├── custom_handler.py           # Stub file for path resolution
└── src/agentllm/
    └── custom_handler.py       # Actual implementation
```

**Why This Pattern:**

LiteLLM's `get_instance_fn()` constructs file paths relative to the config directory:

- Config at root → looks for `./custom_handler.py`
- Handler reference: `custom_handler.agno_handler`
- Stub imports from actual implementation: `from agentllm.custom_handler import agno_handler`

**Docker Layout:**

```
/app/
├── proxy_config.yaml
├── custom_handler.py           # Stub (same as local)
├── agentllm/
│   └── custom_handler.py       # Actual implementation
```

- Same pattern as local dev, ensures consistency across environments

This pattern ensures compatibility across local development and Docker environments while keeping code organized.

### Agent Architecture

**ReleaseManager Wrapper Pattern** (`src/agentllm/agents/release_manager.py`):

- Wraps Agno `Agent` instances with configuration management
- Maintains per-user agents with toolkit isolation
- Intercepts `run()` and `arun()` calls to handle toolkit configuration
- Configuration flow:
  1. Extract configuration from user messages (OAuth codes, API tokens)
  2. Check for required toolkit configurations
  3. Prompt for missing configuration or delegate to wrapped agent
  4. Invalidate and recreate agents when new tools are authorized

**Session Management:**

- Shared SQLite database: `tmp/agno_sessions.db`
- Enables conversation history via `db=shared_db`
- Session/user context extracted from OpenWebUI headers

### Toolkit Configuration System

**Base Architecture** (`src/agentllm/agents/toolkit_configs/base.py`):

- Abstract `BaseToolkitConfig` class for service-agnostic toolkit management
- Each toolkit implements:
  - `is_configured()` - Check if user has configured this toolkit
  - `extract_and_store_config()` - Extract credentials from messages
  - `get_config_prompt()` - Prompt for missing configuration
  - `get_toolkit()` - Return configured toolkit instance
  - `check_authorization_request()` - Detect authorization requests
  - `get_agent_instructions()` - Provide toolkit-specific instructions

**Toolkit Types:**

- **Required:** Prompt immediately on first use (e.g., Google Drive)
- **Optional:** Only prompt when user mentions toolkit features (e.g., Jira)

**Current Implementations:**

- `GoogleDriveConfig` - OAuth-based Google Drive access
- `JiraConfig` - API token-based Jira access

### Token Storage

**Centralized Credential Storage** (`src/agentllm/db/token_storage.py`):

- SQLite-backed storage for OAuth credentials and API tokens
- Reuses Agno's `SqliteDb` engine for single database
- Tables: `jira_tokens`, `gdrive_tokens`
- Operations: `upsert_*_token()`, `get_*_token()`, `delete_*_token()`

### Streaming Support

LiteLLM's `CustomLLM` requires **GenericStreamingChunk format** (not `ModelResponse`):

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

**Implementation:**

- Sync streaming (`streaming()`): Returns complete response as single chunk
- Async streaming (`astreaming()`): True real-time streaming using `agent.arun(stream=True)`

## Project Structure

```
src/agentllm/
├── custom_handler.py              # LiteLLM CustomLLM implementation
├── proxy_config.yaml              # LiteLLM proxy configuration
├── agents/
│   ├── release_manager.py         # ReleaseManager wrapper class
│   └── toolkit_configs/
│       ├── base.py                # Abstract base class
│       ├── gdrive_config.py       # Google Drive OAuth config
│       └── jira_config.py         # Jira API token config
├── tools/
│   ├── gdrive_toolkit.py          # Google Drive tools
│   ├── gdrive_utils.py            # OAuth flow utilities
│   └── jira_toolkit.py            # Jira tools
└── db/
    └── token_storage.py           # SQLite token storage
```

## Adding New Agents

1. Create agent file in `src/agentllm/agents/`:

```python
from agno.agent import Agent
from agno.models.google import Gemini
from agentllm.agents.release_manager import shared_db

def create_my_agent(temperature=None, max_tokens=None, **kwargs):
    model_params = {"id": "gemini-2.5-flash"}
    if temperature is not None:
        model_params["temperature"] = temperature
    if max_tokens is not None:
        model_params["max_tokens"] = max_tokens

    return Agent(
        name="my-agent",
        model=Gemini(**model_params),
        description="My custom agent",
        instructions=["Your instructions"],
        db=shared_db,
        add_history_to_context=True,
        num_history_runs=10,
    )
```

2. Update `custom_handler.py` to import and instantiate new agent

3. Add to `proxy_config.yaml`:

```yaml
- model_name: agno/my-agent
  litellm_params:
    model: agno/my-agent
    custom_llm_provider: agno
```

## Environment Setup

Required environment variables (see `.env.example`):

- `GEMINI_API_KEY` - Required for all models (get from <https://aistudio.google.com/apikey>)
- `LITELLM_MASTER_KEY` - API key for proxy access (default: `sk-agno-test-key-12345`)

## Key Implementation Details

### Session Context Extraction

Session/user context is extracted from multiple sources (priority order):

1. Request body metadata (from OpenWebUI pipe functions)
2. OpenWebUI headers (`X-OpenWebUI-User-Id`, `X-OpenWebUI-Chat-Id`)
3. LiteLLM metadata
4. User field

See `_extract_session_info()` in `custom_handler.py`

### Agent Caching Strategy

- Agents cached by: `(agent_name, temperature, max_tokens, user_id)`
- Per-user isolation ensures credential separation
- Cache invalidation on toolkit authorization changes

### Configuration Flow

1. User sends message
2. ReleaseManager checks for embedded configuration (OAuth codes, tokens)
3. If found: extract, validate, store, invalidate agent cache
4. If required toolkit unconfigured: return prompt
5. If optional toolkit requested but unconfigured: return prompt
6. Otherwise: get/create agent and run

## Testing Approach

Project follows Test-Driven Development (TDD):

1. Write failing test
2. Implement feature
3. Run tests: `nox -s test`
4. Refactor as needed

## Package Manager

This project uses **uv** for dependency management. Always use `uv run` or `uv sync` for Python commands.

## Context7 Documentation Server

**When to use:**

- Working with external libraries/frameworks
- Implementing new integrations or features with third-party tools
- Need current documentation beyond training cutoff
- Troubleshooting library-specific issues

Libraries in this project:

- Agno: mcp__context7__get_library_docs(context7CompatibleLibraryID="/websites/agno")
- LiteLLM: mcp__context7__get_library_docs(context7CompatibleLibraryID="/berriai/litellm")
- OpenWebUI: mcp__context7__get_library_docs(context7CompatibleLibraryID="/websites/openwebui")
