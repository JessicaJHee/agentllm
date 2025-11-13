# Local Development Guide

This guide explains how to run the Sidekick Agent application locally for development and testing.

## Overview

AgentLLM supports two development modes optimized for different workflows. Choose the mode that fits your needs.

## Choosing a Development Mode

```
┌─ Are you modifying proxy or agent code?
│
├─ YES → Development Mode (Local Proxy + Containerized UI)
│         ✓ Instant code reloading
│         ✓ Easy debugging with local tools
│         ✓ Direct log access
│         Command: nox -s proxy (terminal 1)
│                  nox -s dev_local_proxy (terminal 2)
│
└─ NO  → Full Container Mode (Recommended for First-Time Setup)
          ✓ Simplest to start - one command
          ✓ Production-like environment
          ✓ No Python environment needed
          Command: nox -s dev (or nox -s dev_build for first time)
```

### Quick Decision Guide

| Scenario | Recommended Mode |
|----------|------------------|
| First time trying AgentLLM | Full Container |
| Testing existing agents | Full Container |
| Adding/modifying agents | Development Mode |
| Debugging agent behavior | Development Mode |
| Working on toolkit code | Development Mode |
| Creating documentation | Full Container |

## Architecture

```
┌──────────────────────────────────────────────┐
│            Podman Compose                     │
│                                               │
│  ┌─────────────────┐    ┌─────────────────┐ │
│  │   OpenWebUI     │───▶│ LiteLLM Proxy   │ │
│  │   :3000→8080    │    │    :8890        │ │
│  │ (Official Image)│    │ (Custom Build)  │ │
│  └────────┬────────┘    └────────┬────────┘ │
│           │                      │           │
│  ┌────────▼────────┐    ┌────────▼────────┐ │
│  │ openwebui       │    │ litellm-data    │ │
│  │   volume        │    │   volume        │ │
│  └─────────────────┘    └─────────────────┘ │
│                                  │           │
│                         ┌────────▼────────┐ │
│                         │  Local code     │ │
│                         │  (mounted)      │ │
│                         └─────────────────┘ │
└───────────────────────────────────────────────┘
                           │
                ┌──────────▼────────────┐
                │  Google Gemini API    │
                │  (External - HTTPS)   │
                └───────────────────────┘
```

## Quick Start

### Prerequisites

1. **Podman**
   - Install from: https://podman.io/getting-started/installation
   - Verify: `podman compose version`

2. **Google Gemini API Key** (Required)
   - Get from: https://aistudio.google.com/apikey
   - Free tier available

### Setup (5 minutes)

1. **Clone and navigate to the repository**
```bash
cd /path/to/sidekick/agentllm
```

2. **Create environment file**
```bash
cp .env.secrets.template .env.secrets
```

3. **Edit `.env.secrets` and add your API key**
```bash
# Required: Add your Gemini API key
GEMINI_API_KEY=AIzaSy...  # Replace with your actual key

# Optional: Customize master key
LITELLM_MASTER_KEY=sk-agno-test-key-12345

# Optional: Enable OAuth (see OAuth section below)
ENABLE_OAUTH_SIGNUP=false
```

4. **Start the application**
```bash
nox -s dev_build
```

5. **Open your browser**
   - Navigate to: http://localhost:3000
   - Create an account or sign in
   - Start chatting with `agno/release-manager`

That's it! 🎉

## Port Reference

Understanding ports is important for accessing services and configuring connections:

| Service | Internal Port | External Port | Access URL | Notes |
|---------|---------------|---------------|------------|-------|
| **Open WebUI** | 8080 | 3000 | http://localhost:3000 | User interface |
| **LiteLLM Proxy** | 8890 | 8890 | http://localhost:8890 | API endpoint |

**Port Mapping Explanation:**
- **Internal Port**: Port inside the container (used in container-to-container communication)
- **External Port**: Port on your host machine (what you use in browser/curl)
- Mapping notation: `external:internal` (e.g., `3000:8080`)

**Connection URLs:**
- From browser: Use external port (http://localhost:3000)
- From container: Use internal port and service name (http://open-webui:8080)
- From host machine: Use external port (http://localhost:8890)

## Development Commands (via Nox)

**Note:** Nox automatically detects whether to use Podman - no configuration needed!

The project uses [Nox](https://nox.thea.codes/) for managing development tasks. All Podman Compose operations are available as nox sessions.

### Available Sessions

| Command | Description |
|---------|-------------|
| `nox -s dev` | Start environment (reuses existing images) |
| `nox -s dev_build` | Build and start (forces rebuild) |
| `nox -s dev_detach` | Start in background with health checks |
| `nox -s dev_logs` | View container logs |
| `nox -s dev_stop` | Stop all containers |
| `nox -s dev_clean` | Stop containers and remove all data |

**Quick tip:** Use `nox -s dev` for daily work (faster), and `nox -s dev_build` only when you modify dependencies or need a clean build.

### Examples

```bash
# First time or after dependency changes
nox -s dev_build

# Quick start (reuses existing images)
nox -s dev

# Start in background
nox -s dev_detach

# View logs
nox -s dev_logs

# View logs for specific service
nox -s dev_logs -- litellm-proxy

# Stop services
nox -s dev_stop

# Clean everything (deletes data!)
nox -s dev_clean
```

## Manual Podman Compose Commands

If you prefer to use podman compose directly:

```bash
# Start services (foreground)
podman compose up

# Start services (background)
podman compose up -d

# Build and start
podman compose up --build

# Stop services
podman compose down

# Stop and remove volumes (deletes data)
podman compose down -v

# View logs
podman compose logs -f

# View logs for specific service
podman compose logs -f litellm-proxy
podman compose logs -f open-webui

# Restart a service
podman compose restart litellm-proxy

# Rebuild a specific service
podman compose build litellm-proxy
```

## Development Workflow

### Hot Reloading

The local setup mounts your source code into the container, allowing for **live code updates**:

```yaml
volumes:
  - ./src/agentllm:/app/agentllm  # Your code is mounted here
```

**To apply code changes:**

1. Edit files in `src/agentllm/`
2. Restart the LiteLLM service:
   ```bash
   podman compose restart litellm-proxy
   ```

### Viewing Logs

Monitor what's happening in real-time:

```bash
# All services
podman compose logs -f

# Just LiteLLM proxy
podman compose logs -f litellm-proxy

# Just OpenWebUI
podman compose logs -f open-webui
```

### Accessing the Database

The SQLite database is stored in a Podman volume. To access it:

```bash
# Copy database to local filesystem
podman compose cp litellm-proxy:/app/tmp/agno_sessions.db ./agno_sessions.db

# Or exec into the container
podman compose exec litellm-proxy /bin/bash
cd /app/tmp
sqlite3 agno_sessions.db
```

### Inspecting Containers

```bash
# List running containers
podman compose ps

# Exec into litellm-proxy
podman compose exec litellm-proxy bash

# Exec into open-webui
podman compose exec open-webui bash
```

## Configuration

### Environment Variables

All configuration is in `.env.secrets`. See [CONFIGURATION.md](CONFIGURATION.md) for detailed setup instructions.

**Required variables:**
```bash
GEMINI_API_KEY=AIzaSy...  # Get from https://aistudio.google.com/apikey
```

**Optional OAuth and integrations:**
```bash
# Open WebUI OAuth (Google sign-in)
ENABLE_OAUTH_SIGNUP=false
OAUTH_CLIENT_ID=xxx.apps.googleusercontent.com
OAUTH_CLIENT_SECRET=xxx

# Google Drive (for Release Manager agent)
GDRIVE_CLIENT_ID=xxx.apps.googleusercontent.com
GDRIVE_CLIENT_SECRET=xxx

# Jira (for Release Manager agent)
JIRA_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your.email@example.com
JIRA_API_TOKEN=xxx
```

**Setup guides:**
- **Open WebUI OAuth**: See [CONFIGURATION.md#open-webui-oauth-setup](CONFIGURATION.md#open-webui-oauth-setup)
- **Google Drive**: See [CONFIGURATION.md#google-drive-oauth](CONFIGURATION.md#google-drive-oauth)
- **Jira**: See [CONFIGURATION.md#jira-configuration](CONFIGURATION.md#jira-configuration)
- **Extended System Prompts**: See [CONFIGURATION.md#extended-system-prompts](CONFIGURATION.md#extended-system-prompts)

All configuration details, OAuth setup instructions, and troubleshooting are documented in [CONFIGURATION.md](CONFIGURATION.md).

## Data Persistence

### Volumes

Two Podman volumes persist data across restarts:

1. **`litellm-data`**: SQLite database and Google Drive workspace
   - Database: `/app/tmp/agno_sessions.db`
   - Workspace: `/app/tmp/gdrive_workspace/`

2. **`openwebui`**: User accounts and UI settings
   - Data: `/app/backend/data`

### Backing Up Data

```bash
# Backup database
podman compose cp litellm-proxy:/app/tmp/agno_sessions.db ./backup-$(date +%Y%m%d).db

# Restore database
podman compose cp ./backup-20250107.db litellm-proxy:/app/tmp/agno_sessions.db
podman compose restart litellm-proxy
```

### Resetting Data

```bash
# Remove all data (fresh start)
nox -s dev_clean

# Or manually
podman compose down -v
```

## Troubleshooting

### Container won't start

**Check logs:**
```bash
podman compose logs litellm-proxy
```

**Common issues:**
- Missing `GEMINI_API_KEY` in `.env.secrets`
- Invalid API key
- Port 8890 or 3000 already in use

### Port already in use

Change ports in `compose.yaml`:
```yaml
services:
  litellm-proxy:
    ports:
      - "8891:8890"  # Use port 8891 instead

  open-webui:
    ports:
      - "3001:8080"  # Use port 3001 instead
```

Then update the connection in OpenWebUI environment:
```yaml
OPENAI_API_BASE_URLS: "http://litellm-proxy:8890/v1"  # Keep this the same (internal)
```

### Health check failing

The LiteLLM container has a health check that calls `/health`:

```bash
# Check health endpoint manually
curl http://localhost:8890/health

# View health status
podman compose ps
```

**If unhealthy:**
1. Check logs: `podman compose logs litellm-proxy`
2. Verify `GEMINI_API_KEY` is set
3. Ensure config file is mounted correctly

### OAuth not working

1. **Verify redirect URI** matches exactly:
   ```
   http://localhost:3000/oauth/google/callback
   ```

2. **Check environment variables**:
   ```bash
   podman compose exec open-webui env | grep OAUTH
   ```

3. **Restart OpenWebUI**:
   ```bash
   podman compose restart open-webui
   ```

### Database locked errors

SQLite doesn't support concurrent writes. Ensure:
- Only one LiteLLM container is running
- No manual database access while container is running

```bash
# Check running containers
podman compose ps

# Should show only ONE litellm-proxy container
```

### Code changes not reflected

After editing code in `src/agentllm/`:

```bash
# Restart the service
podman compose restart litellm-proxy

# Or rebuild if dependencies changed
podman compose up --build -d
```

## Performance Tips

### Faster Rebuilds

Only rebuild when dependencies change:
```bash
# Code changes only - just restart
podman compose restart litellm-proxy

# Dependencies changed - rebuild
podman compose build litellm-proxy
podman compose up -d
```

### Resource Limits

If containers use too much memory/CPU, add limits to `compose.yaml`:

```yaml
services:
  litellm-proxy:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

## Testing

### Health Check

```bash
# LiteLLM health
curl http://localhost:8890/health

# OpenWebUI
curl http://localhost:3000/health
```

### API Testing

```bash
# List models
curl http://localhost:8890/v1/models \
  -H "Authorization: Bearer sk-agno-test-key-12345"

# Chat completion
curl http://localhost:8890/v1/chat/completions \
  -H "Authorization: Bearer sk-agno-test-key-12345" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "agno/release-manager",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Differences from Production

| Feature | Local Development | OpenShift Production |
|---------|------------------|----------------------|
| Build | `Dockerfile.local` | `openshift/Dockerfile` |
| Code mounting | ✅ Live mounted | ❌ Baked into image |
| User | root (dev convenience) | Non-root (security) |
| Health checks | Basic curl | Full K8s probes |
| Replicas | Single container | Multiple OpenWebUI pods |
| TLS | HTTP only | HTTPS with edge termination |
| Secrets | `.env.secrets` file | Kubernetes Secrets |

## Next Steps

### Deploy to OpenShift

When ready for production, see [openshift/README.md](openshift/README.md) for deployment instructions.

### Customize Configuration

- Edit `src/agentllm/proxy_config.yaml` to add models
- Modify agent behavior in `src/agentllm/custom_handler.py`
- Adjust UI settings via OpenWebUI environment variables

### Add Features

1. Make changes to code in `src/agentllm/`
2. Restart services: `podman compose restart litellm-proxy`
3. Test in browser at http://localhost:3000
4. Commit changes when ready

## Getting Help

- View logs: `podman compose logs -f`
- Check container status: `podman compose ps`
- Inspect environment: `podman compose exec litellm-proxy env`
- Test API: `curl http://localhost:8890/health`

## Clean Up

```bash
# Stop services (keeps data)
nox -s dev_stop

# Remove everything (including data)
nox -s dev_clean
```
