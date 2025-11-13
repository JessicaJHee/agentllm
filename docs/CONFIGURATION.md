# Configuration Guide

This guide covers all configuration options for AgentLLM, including environment variables, OAuth setup, and advanced features.

## Table of Contents

- [Environment Files](#environment-files)
- [Required Configuration](#required-configuration)
- [LiteLLM Proxy Settings](#litellm-proxy-settings)
- [Open WebUI Configuration](#open-webui-configuration)
- [Google Drive OAuth](#google-drive-oauth)
- [Jira Configuration](#jira-configuration)
- [Extended System Prompts](#extended-system-prompts)
- [Per-Environment Configuration](#per-environment-configuration)

## Environment Files

AgentLLM supports two approaches for managing environment variables:

### Environment Files (Recommended for Local Development)

```bash
cp .env.secrets.template .env.secrets
# Edit .env.secrets with all your secrets
```

The project uses split environment files:
- `.env.shared` - Non-sensitive defaults (tracked in git)
- `.env.secrets` - Secrets and API keys (gitignored)

### Split Configuration (Recommended for Production)

```bash
# .env.shared - Non-sensitive configuration (can be committed to git)
WEBUI_NAME=Sidekick Agent
DEFAULT_MODELS=agno/release-manager
ENABLE_SIGNUP=false

# .env.secrets - Sensitive credentials (NEVER commit to git)
GEMINI_API_KEY=AIzaSy...
LITELLM_MASTER_KEY=sk-agno-...
OAUTH_CLIENT_SECRET=...
```

Podman Compose automatically loads both files:
```yaml
env_file:
  - .env.shared   # Team-wide defaults
  - .env.secrets  # Your personal credentials
```

**Benefits:**
- Team can share `.env.shared` via git
- Each developer maintains personal `.env.secrets`
- Production uses ConfigMaps (.env.shared) + Secrets (.env.secrets)

## Required Configuration

These variables **must** be set for AgentLLM to function:

### `GEMINI_API_KEY`

Google Gemini API key for all AI models (agents and direct Gemini models).

```bash
GEMINI_API_KEY=AIzaSy...your_key_here
```

**How to get:**
1. Visit [Google AI Studio](https://aistudio.google.com/apikey)
2. Click "Get API key"
3. Click "Create API key in new project" (or use existing)
4. Copy the key

**Used by:**
- All Agno agents (`agno/release-manager`, `agno/demo-agent`)
- Direct Gemini models (`gemini-2.5-pro`, `gemini-2.5-flash`)

### `LITELLM_MASTER_KEY`

API key for authenticating to the LiteLLM proxy.

```bash
LITELLM_MASTER_KEY=sk-agno-test-key-12345
```

**Default:** `sk-agno-test-key-12345` (fine for local development)

**Production:** Generate a strong random key:
```bash
openssl rand -base64 32
# Use the output as your LITELLM_MASTER_KEY
```

**Used in requests:**
```bash
curl -H "Authorization: Bearer sk-agno-test-key-12345" ...
```

## LiteLLM Proxy Settings

### `LITELLM_PORT`

Port for the LiteLLM proxy server.

```bash
LITELLM_PORT=8890
```

**Default:** `8890`

**Note:** If you change this, also update `OPENAI_API_BASE_URL` accordingly.

## Open WebUI Configuration

### Connection to LiteLLM

#### `OPENAI_API_BASE_URL`

**Most important variable** - Controls how Open WebUI connects to the LiteLLM proxy.

```bash
# Local development (proxy running locally)
OPENAI_API_BASE_URL=http://host.docker.internal:8890/v1

# Production (proxy in container)
OPENAI_API_BASE_URL=http://litellm-proxy:8890/v1
```

**How it works:**
- Open WebUI runs in a container
- Needs to reach proxy which might be on host machine or another container
- `host.docker.internal` is a special DNS name that resolves to the host machine
- On Linux, this is automatically configured via `extra_hosts` in compose.yaml

**Mode selection:**
- `nox -s dev_local_proxy` → Uses value from `.env.secrets` (local proxy)
- `nox -s dev-full` → Overrides to `http://litellm-proxy:8890/v1` (both containerized)

### Branding

#### `WEBUI_NAME`

Display name for the web interface.

```bash
WEBUI_NAME=Sidekick Agent
```

**Default:** `Sidekick Agent`

Appears in:
- Browser tab title
- Header bar
- Login page

#### `WEBUI_URL`

External URL for accessing Open WebUI (used for OAuth callbacks).

```bash
WEBUI_URL=http://localhost:3000
```

**Port explanation:**
- External port: `3000` (what you access in browser)
- Internal port: `8080` (inside container)
- Mapping: `3000:8080` in compose.yaml

**Production example:**
```bash
WEBUI_URL=https://agents.yourdomain.com
```

### Default Models

#### `DEFAULT_MODELS`

Comma-separated list of default models to show users.

```bash
DEFAULT_MODELS=agno/release-manager
```

**Multiple models:**
```bash
DEFAULT_MODELS=agno/release-manager,agno/demo-agent
```

### Authentication

#### `WEBUI_AUTH`

Enable/disable authentication.

```bash
WEBUI_AUTH=true
```

**Values:**
- `true` - Require login (recommended)
- `false` - No authentication (only for testing)

#### `ENABLE_SIGNUP`

Allow users to create accounts via signup form.

```bash
ENABLE_SIGNUP=false
```

**When to use:**
- `false` - OAuth-only signup (production)
- `true` - Local account creation allowed

#### `ENABLE_OAUTH_SIGNUP`

Enable Google OAuth login.

```bash
ENABLE_OAUTH_SIGNUP=true
```

See [Open WebUI OAuth Setup](#open-webui-oauth-setup) for configuration.

### Security Settings

#### Session and Auth Cookies

```bash
# Development (HTTP)
WEBUI_SESSION_COOKIE_SAME_SITE=lax
WEBUI_SESSION_COOKIE_SECURE=false
WEBUI_AUTH_COOKIE_SECURE=false

# Production (HTTPS - REQUIRED)
WEBUI_SESSION_COOKIE_SAME_SITE=strict
WEBUI_SESSION_COOKIE_SECURE=true
WEBUI_AUTH_COOKIE_SECURE=true
```

**Important:** Set `SECURE=true` only when using HTTPS. Setting it with HTTP will break authentication.

### Logging

#### `LOG_LEVEL`, `UVICORN_LOG_LEVEL`, `GLOBAL_LOG_LEVEL`

Control verbosity and **content security**.

```bash
# Development
LOG_LEVEL=DEBUG
UVICORN_LOG_LEVEL=debug
GLOBAL_LOG_LEVEL=DEBUG

# Production
LOG_LEVEL=INFO
UVICORN_LOG_LEVEL=info
GLOBAL_LOG_LEVEL=INFO
```

**Security impact:**
- `DEBUG` - Logs full message content (user messages, agent responses)
- `INFO` - Logs only metadata (content length, types)

**Never use DEBUG in production** - it will log sensitive user data!

### Disabled Features

```bash
# We use agent-level tools instead of OpenWebUI RAG
ENABLE_RAG_WEB_SEARCH=false
ENABLE_OLLAMA_API=false
ENABLE_COMMUNITY_SHARING=false
OFFLINE_MODE=false  # Set to true in production to prevent external downloads
```

## Open WebUI OAuth Setup

Allow users to log in with their Google accounts.

### Prerequisites

- Google Cloud project
- OAuth 2.0 credentials

### Setup Steps

1. **Go to [Google Cloud Console](https://console.cloud.google.com)**

2. **Create or select a project**

3. **Enable APIs (if not already enabled)**
   - No special APIs needed for basic OAuth

4. **Create OAuth 2.0 Credentials:**
   - Navigate to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth 2.0 Client ID"
   - Application type: **Web application**
   - Name: `AgentLLM Open WebUI`

5. **Add Authorized Redirect URI:**
   ```
   http://localhost:3000/oauth/oidc/callback
   ```

   **Production:**
   ```
   https://agents.yourdomain.com/oauth/oidc/callback
   ```

   **Critical:** URI must exactly match `${WEBUI_URL}/oauth/oidc/callback`

6. **Copy credentials to `.env.secrets`:**
   ```bash
   ENABLE_OAUTH_SIGNUP=true
   OAUTH_CLIENT_ID=123456789-abc.apps.googleusercontent.com
   OAUTH_CLIENT_SECRET=GOCSPX-...
   ```

7. **Restart services:**
   ```bash
   nox -s dev_stop
   nox -s dev_build
   ```

8. **Test:**
   - Visit http://localhost:3000
   - Click "Sign in with Google"
   - Authorize the application

## Google Drive OAuth

Enables the Release Manager agent to access Google Drive (read/write documents).

### Setup Steps

1. **Go to [Google Cloud Console](https://console.cloud.google.com)**

2. **Create or select a project** (can use same project as Open WebUI OAuth)

3. **Enable Google Drive API:**
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Drive API"
   - Click "Enable"

4. **Create OAuth 2.0 Credentials:**
   - Navigate to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth 2.0 Client ID"
   - Application type: **Web application**
   - Name: `AgentLLM Google Drive`

5. **Add Authorized Redirect URI:**
   ```
   http://localhost
   ```

   **Note:** Just `http://localhost`, not a full URL. This is for the local OAuth flow.

6. **Copy credentials to `.env.secrets`:**
   ```bash
   GDRIVE_CLIENT_ID=123456789-xyz.apps.googleusercontent.com
   GDRIVE_CLIENT_SECRET=GOCSPX-...
   ```

7. **Restart services:**
   ```bash
   nox -s dev_stop
   nox -s dev_build
   ```

### User Flow

1. User interacts with Release Manager agent
2. Agent prompts: "I need access to Google Drive"
3. Agent provides authorization URL
4. User clicks URL and authorizes
5. User copies authorization code
6. User sends code to agent
7. Agent stores credentials and can now access Google Drive

**Per-user credentials:** Each user authorizes separately. Credentials are stored in SQLite database.

## Jira Configuration

Enables the Release Manager agent to query and update Jira tickets.

### Setup Steps

1. **Create Jira API Token:**
   - Visit [Atlassian Account Settings](https://id.atlassian.com/manage-profile/security/api-tokens)
   - Click "Create API token"
   - Give it a label: `AgentLLM Release Manager`
   - Copy the token (you won't see it again!)

2. **Configure environment variables:**
   ```bash
   # These are optional - agent will prompt users for them
   JIRA_URL=https://your-domain.atlassian.net
   JIRA_USERNAME=your.email@example.com
   JIRA_API_TOKEN=your_api_token_here
   ```

3. **Restart services:**
   ```bash
   nox -s dev_stop
   nox -s dev_build
   ```

### User Flow

If environment variables are **not** set, agent will prompt each user:

1. User interacts with Release Manager
2. Agent asks for Jira configuration
3. User provides:
   - Jira URL: `https://your-domain.atlassian.net`
   - Jira email: `your.email@example.com`
   - Jira API token: `your_token`
4. Agent stores credentials (per-user)

**Recommendation:** For production, set global env vars. For development, use per-user configuration.

## Extended System Prompts

Allows maintaining agent instructions in Google Docs instead of code.

### Overview

- **Embedded prompt:** Agent's core identity and capabilities (in code)
- **Extended prompt:** Operational instructions, Jira queries, workflows (in Google Doc)

See [CLAUDE.md - Release Manager System Prompt Architecture](../CLAUDE.md#release-manager-system-prompt-architecture) for design rationale.

### Setup

1. **Create Google Doc:**
   - Copy content from `docs/templates/release_manager_system_prompt.md`
   - Create new Google Doc
   - Paste content and customize for your team

2. **Share document:**
   - Click "Share"
   - Give read access to all agent users
   - Copy document URL

3. **Configure environment:**
   ```bash
   RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL=https://docs.google.com/document/d/1ABC123xyz/edit
   # Or just the ID:
   RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL=1ABC123xyz
   ```

4. **Verify prerequisites:**
   - `GDRIVE_CLIENT_ID` and `GDRIVE_CLIENT_SECRET` must be set
   - Users must authorize Google Drive access
   - Document must be readable by user's Google account

5. **Restart services:**
   ```bash
   nox -s dev_stop
   nox -s dev_build
   ```

### Update Workflow

1. Edit Google Doc
2. Save changes
3. Agent fetches new version on next recreation
   - Happens when user re-authorizes Google Drive
   - Or when application restarts

**No code deployment needed!**

### Separate Dev/Prod Prompts

```bash
# Development
RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL=https://docs.google.com/document/d/DEV_DOC_ID

# Production
RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL=https://docs.google.com/document/d/PROD_DOC_ID
```

Test prompt changes in dev before deploying to production.

## Per-Environment Configuration

### Local Development

```bash
# .env
GEMINI_API_KEY=AIzaSy...
LITELLM_MASTER_KEY=sk-agno-test-key-12345
OPENAI_API_BASE_URL=http://host.docker.internal:8890/v1
WEBUI_URL=http://localhost:3000
LOG_LEVEL=DEBUG
WEBUI_SESSION_COOKIE_SECURE=false
ENABLE_SIGNUP=true
```

### Production

```bash
# .env or Kubernetes ConfigMap/Secrets
GEMINI_API_KEY=<from-secret>
LITELLM_MASTER_KEY=<strong-random-key>
OPENAI_API_BASE_URL=http://litellm-proxy-service:8890/v1
WEBUI_URL=https://agents.yourdomain.com
LOG_LEVEL=INFO
WEBUI_SESSION_COOKIE_SECURE=true
ENABLE_SIGNUP=false
ENABLE_OAUTH_SIGNUP=true
OFFLINE_MODE=true
```

## Validation

Check your configuration:

```bash
# Verify .env exists
ls -la .env

# Check required variables (without exposing values)
grep -q "GEMINI_API_KEY" .env && echo "✓ GEMINI_API_KEY set" || echo "✗ GEMINI_API_KEY missing"
grep -q "LITELLM_MASTER_KEY" .env && echo "✓ LITELLM_MASTER_KEY set" || echo "✗ LITELLM_MASTER_KEY missing"
```

The `nox -s dev_build` command automatically validates required variables before starting.

## Reference

See `.env.secrets.template` for:
- All available variables
- Detailed inline comments
- Example values
- Default settings

## Security Best Practices

1. **Never commit `.env.secrets` to git**
   - Already in `.gitignore`
   - Use `.env.shared` for team-wide non-sensitive config

2. **Use strong keys in production**
   ```bash
   openssl rand -base64 32  # Generate strong keys
   ```

3. **Enable cookie security in production**
   ```bash
   WEBUI_SESSION_COOKIE_SECURE=true
   WEBUI_AUTH_COOKIE_SECURE=true
   ```

4. **Disable debug logging in production**
   ```bash
   LOG_LEVEL=INFO  # Prevents logging user messages
   ```

5. **Restrict signups in production**
   ```bash
   ENABLE_SIGNUP=false
   ENABLE_OAUTH_SIGNUP=true  # OAuth only
   ```

## Troubleshooting

### Configuration Not Loading

**Issue:** Changes to `.env.secrets` not reflected

**Solution:**
```bash
nox -s dev_stop    # Stop containers
nox -s dev_build   # Rebuild and restart
```

### OAuth Redirect URI Mismatch

**Error:** `redirect_uri_mismatch`

**Solution:**
1. Check `WEBUI_URL` matches your access URL exactly
2. In Google Cloud Console, verify redirect URI:
   ```
   ${WEBUI_URL}/oauth/oidc/callback
   ```
3. For Open WebUI OAuth: `/oauth/oidc/callback`
4. For Google Drive OAuth: `http://localhost`

### Google Drive Access Denied

**Error:** "Failed to fetch extended system prompt"

**Solution:**
1. Verify document URL in `RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL`
2. Check document sharing (user must have read access)
3. Ensure user has authorized Google Drive in agent
4. Check logs: `nox -s dev_logs -- litellm-proxy`

## Next Steps

- [QUICKSTART.md](QUICKSTART.md) - Get started quickly
- [DEVELOPMENT.md](DEVELOPMENT.md) - Development workflows
- [Creating Agents](agents/creating-agents.md) - Build custom agents
- [CLAUDE.md](../CLAUDE.md) - Technical architecture
