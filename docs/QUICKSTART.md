# Quick Start Guide

This guide will help you get AgentLLM up and running in under 10 minutes.

## Prerequisites

Before you begin, make sure you have:

1. **Python 3.11 or later** - [Download Python](https://www.python.org/downloads/)

2. **uv package manager** - [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
   ```bash
   # One-liner install (Mac/Linux)
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **nox task automation** - [Install nox](https://nox.thea.codes/en/stable/tutorial.html#installation)
   ```bash
   # Install with uv (recommended)
   uv tool install nox
   ```

4. **Podman** - [Install Podman](https://podman.io/getting-started/installation)
   ```bash
   # Mac (via Homebrew)
   brew install podman
   podman machine init
   podman machine start

   # Linux (Fedora/RHEL/CentOS)
   sudo dnf install podman

   # Ubuntu/Debian
   sudo apt install podman
   ```

5. **Google Gemini API Key** - [Get your free key](https://aistudio.google.com/apikey)

> **Note:** This project uses Podman for containerization. Podman is a daemonless container engine that's compatible with Docker's OCI format but more secure.

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/durandom/agentllm
cd agentllm
```

### Step 2: Install Dependencies

```bash
uv sync
```

This will:
- Create a virtual environment
- Install all Python dependencies
- Set up the project for development

### Step 3: Configure Environment

```bash
cp .env.secrets.template .env.secrets
```

Edit the `.env.secrets` file and set your Google Gemini API key:

```bash
# Required: Add your Gemini API key
GEMINI_API_KEY=AIzaSy...your_actual_key_here
```

**How to get your API key:**
1. Visit [Google AI Studio](https://aistudio.google.com/apikey)
2. Click "Get API key"
3. Click "Create API key in new project" (or select existing project)
4. Copy the key and paste it in `.env.secrets`

### Step 4: Start Everything

```bash
nox -s dev_build  # First time: builds containers
```

This command will:
- Build the LiteLLM proxy container
- Start the Open WebUI container
- Connect them together
- Display progress and logs

**For subsequent starts**, use `nox -s dev` (faster, reuses existing images):
```bash
nox -s dev  # Quick start without rebuild
```

Wait for the message:
```
✅ LiteLLM Proxy is healthy
```

### Step 5: Access Open WebUI

Open your browser to: **http://localhost:3000**

On first visit:
1. Click "Sign up"
2. Create an account (this is local only, no data leaves your machine)
3. The first user automatically becomes admin

## First Interaction

### Test the Release Manager Agent

1. In Open WebUI, click the **model selector** (top of the page)
2. Select `agno/release-manager`
3. Type a message:
   ```
   Hello! What can you help me with?
   ```
4. The agent will respond with its capabilities

### Test the Demo Agent

1. Click the model selector
2. Select `agno/demo-agent`
3. Type:
   ```
   My favorite color is blue
   ```
4. The agent will configure itself and offer to create color palettes

## Verify Everything is Working

### Check Available Models

```bash
curl -X GET http://127.0.0.1:8890/v1/models \
  -H "Authorization: Bearer sk-agno-test-key-12345"
```

You should see:
```json
{
  "data": [
    {"id": "agno/release-manager"},
    {"id": "agno/demo-agent"},
    {"id": "gemini-2.5-pro"},
    {"id": "gemini-2.5-flash"}
  ]
}
```

### Test Direct API Request

```bash
curl -X POST http://localhost:8890/v1/chat/completions \
  -H "Authorization: Bearer sk-agno-test-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "agno/demo-agent",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Troubleshooting First-Run Issues

### Port Already in Use

**Error:** `Bind for 0.0.0.0:3000 failed: port is already allocated`

**Solution:**
```bash
# Find what's using the port
lsof -i :3000

# Kill the process or change the port in compose.yaml
```

### API Key Not Set

**Error:** `GEMINI_API_KEY is not set in .env`

**Solution:**
1. Ensure you've created `.env.secrets` from `.env.secrets.template`
2. Replace `AIzaSy...` with your actual API key
3. Save the file and restart: `nox -s dev_build`

### Container Won't Start

**Error:** Podman not running or permission denied

**Solution:**
```bash
# Mac: Start Podman machine
podman machine start

# Linux: Start Podman service (if needed)
sudo systemctl start podman
sudo systemctl start podman  # Linux
```

### Can't Access http://localhost:3000

**Issue:** Browser shows "This site can't be reached"

**Solutions:**
1. **Check container is running:**
   ```bash
   podman ps
   ```
   Look for `open-webui` container with status `Up`

2. **Check port mapping:**
   ```bash
   podman ps | grep open-webui
   # Should show: 0.0.0.0:3000->8080/tcp
   ```

3. **View logs:**
   ```bash
   nox -s dev_logs -- open-webui
   ```

### Agent Doesn't Respond

**Issue:** Message sent but no response from agent

**Possible Causes:**
1. **Invalid API key** - Check `.env.secrets` has correct `GEMINI_API_KEY`
2. **API quota exceeded** - Check [Google AI Studio](https://aistudio.google.com/apikey) for quota limits
3. **Network issue** - Check proxy logs: `nox -s dev_logs -- litellm-proxy`

## Next Steps

### Configure Optional Features

**Google Drive Integration** (for Release Manager):
1. See [CONFIGURATION.md](CONFIGURATION.md#google-drive-oauth) for setup
2. Enables the Release Manager to read/write Google Docs

**Jira Integration** (for Release Manager):
1. See [CONFIGURATION.md](CONFIGURATION.md#jira-configuration) for setup
2. Enables querying and updating Jira tickets

### Development Mode

If you want to modify agent code with hot reload:

**Terminal 1** - Start local proxy:
```bash
nox -s proxy
```

**Terminal 2** - Start Open WebUI:
```bash
nox -s dev_local_proxy
```

Now when you edit agent code, the proxy automatically reloads.

See [DEVELOPMENT.md](DEVELOPMENT.md) for details.

### Create Your Own Agent

Follow the [Creating Agents](agents/creating-agents.md) guide to build custom agents with specialized tools.

## Common Commands Reference

```bash
# Start everything (recommended)
nox -s dev_build

# Start in background
nox -s dev_build -- -d

# View logs
nox -s dev_logs              # All services
nox -s dev_logs -- open-webui  # Specific service

# Stop containers (keeps data)
nox -s dev_stop

# Clean everything (deletes data)
nox -s dev_clean

# Run tests
nox -s test
```

## Getting Help

- **Documentation**: See [README.md](../README.md) for overview
- **Development**: See [DEVELOPMENT.md](DEVELOPMENT.md) for advanced workflows
- **Configuration**: See [CONFIGURATION.md](CONFIGURATION.md) for environment variables
- **Architecture**: See [CLAUDE.md](../CLAUDE.md) for technical details

## Summary

You've successfully:
- ✅ Installed AgentLLM and its dependencies
- ✅ Configured your Gemini API key
- ✅ Started the containerized stack
- ✅ Accessed Open WebUI
- ✅ Tested agents (Release Manager and Demo Agent)

You're ready to start using Agno agents through the OpenAI-compatible API!
