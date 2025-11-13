# Release Manager Agent

## Overview

The Release Manager is the primary AI agent in AgentLLM, designed to help users with software releases, changelogs, and general assistance tasks. It wraps an Agno `Agent` instance with user-specific toolkit configuration management and dynamic system prompt loading.

## Features

- **User-specific agent instances**: Each user gets their own agent with isolated credentials
- **Dynamic toolkit configuration**: Supports Google Drive, Jira, and other toolkits
- **Extended system prompt loading**: Fetch additional instructions from Google Docs
- **Session management**: Conversation history stored in SQLite
- **Agent caching**: Agents cached per user for performance

## Architecture

```
┌─────────────────────────────────────────────────────┐
│ ReleaseManager (Wrapper)                            │
├─────────────────────────────────────────────────────┤
│ • Configuration management                          │
│ • Toolkit orchestration                             │
│ • System prompt composition                         │
│ • Agent caching (per user_id)                       │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │ Agno Agent     │
         │ (per user)     │
         └────────────────┘
```

## System Prompt Composition

The Release Manager builds the agent's system prompt in the following order:

1. **Base Instructions** (minimal, built-in)
   ```
   - You are a helpful AI assistant.
   - Answer questions and help users with various tasks.
   - Use markdown formatting for structured output.
   - Be concise and clear in your responses.
   ```

2. **Extended Instructions** (from Google Docs, optional)
   - Fetched from a Google Doc specified by `RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL`
   - Cached per user until agent invalidation
   - See "Extended System Prompt" section below

3. **Toolkit-Specific Instructions** (dynamic, based on configured toolkits)
   - Google Drive usage instructions (if configured)
   - Jira integration instructions (if configured)
   - Other toolkit instructions as they're added

## Extended System Prompt

### Overview

The Release Manager can fetch additional system prompt instructions from a Google Doc. This allows you to:

- Customize agent behavior without code changes
- Update instructions in real-time by editing the Google Doc
- Share prompts across development teams
- Version control prompts using Google Docs revision history

### Configuration

#### 1. Environment Variable

Set the `RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL` environment variable in your `.env.secrets` file:

```bash
# Full URL format
RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL=https://docs.google.com/document/d/1ABC123xyz/edit

# Or just the document ID
RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL=1ABC123xyz
```

#### 2. Prerequisites

- **Google Drive must be configured**: Users must have authorized Google Drive access (via `GDRIVE_CLIENT_ID`/`GDRIVE_CLIENT_SECRET`)
- **Document access**: Users must have read access to the specified Google Doc
- **Document format**: Must be a Google Docs document (not Sheets or Slides)

### How It Works

#### Fetch and Cache Flow

```
1. User creates first message
   ↓
2. Agent creation triggered
   ↓
3. Check if RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL is set
   ↓ (yes)
4. Check if user has Google Drive configured
   ↓ (yes)
5. Check cache for this user's extended prompt
   ↓ (miss)
6. Fetch document content via Google Drive API
   ↓
7. Convert to markdown (automatic)
   ↓
8. Cache content for this user
   ↓
9. Append to agent instructions
   ↓
10. Create agent with combined instructions
```

#### Subsequent Requests

- **Cache hit**: Extended prompt retrieved from cache (no API call)
- **Fast**: No performance impact after first fetch

#### Cache Invalidation

The cached extended prompt is invalidated when:

1. **User authorizes a new toolkit** (e.g., Google Drive, Jira)
   - Triggers `_invalidate_agent()` which clears both agent and system prompt cache

2. **Agent is manually invalidated** (future enhancement)

After invalidation, the next agent creation will fetch a fresh copy from Google Docs.

### Error Handling

If fetching the extended prompt fails, **agent creation will fail** with a clear error message. Common failure scenarios:

| Error | Cause | Solution |
|-------|-------|----------|
| `RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL environment variable not set` | Environment variable missing | Set the variable in `.env.secrets` |
| `Google Drive is not configured for user {user_id}` | User hasn't authorized Google Drive | User must complete OAuth flow |
| `Document at {url} returned empty content` | Document is empty or inaccessible | Check document permissions and content |
| `Failed to fetch extended system prompt from {url}` | Network error, invalid URL, or API error | Check URL, network, and Google Drive API status |

### Document Format

The Google Doc content is automatically converted to **markdown** format. You can use:

- **Headings**: `# Header`, `## Subheader`
- **Lists**: Bullet points and numbered lists
- **Bold/Italic**: `**bold**`, `*italic*`
- **Code**: Inline `` `code` `` and code blocks
- **Links**: `[text](url)`

#### Example Google Doc Structure

```markdown
# Release Manager Extended Instructions

## Your Role
You are an expert software release manager specializing in changelog generation,
semantic versioning, and release automation.

## Guidelines
- Always follow semantic versioning (semver) principles
- Generate changelogs in Keep a Changelog format
- Ask for clarification when release scope is unclear

## Tools Usage
- Use Google Drive tools to read existing changelog files
- Use Jira tools to fetch issue details when available
- Cross-reference commit messages with issue tracking

## Output Format
All changelogs should follow this structure:
...
```

### Best Practices

1. **Keep it focused**: Extended prompts should complement, not duplicate, base instructions
2. **Use clear sections**: Organize with markdown headings for readability
3. **Version your changes**: Use Google Docs revision history to track prompt changes
4. **Test changes**: After updating the doc, invalidate the agent cache to test new instructions
5. **Monitor length**: Very long prompts may impact token usage and cost

### Troubleshooting

#### Extended prompt not loading

1. Check environment variable is set: `echo $RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL`
2. Verify user has Google Drive configured: Check OAuth flow completion
3. Check document permissions: User must have at least "Viewer" access
4. Check logs: Look for "Fetching extended system prompt" and error messages

#### Stale prompt after document update

The extended prompt is cached per user. To force a refresh:
- Currently: User must authorize a new toolkit (triggers cache invalidation)
- Future: Manual cache refresh endpoint (planned enhancement)

#### Agent creation fails with prompt error

If agent creation consistently fails:
1. Temporarily remove `RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL` to isolate the issue
2. Verify the Google Doc URL/ID is correct
3. Check document isn't corrupted or inaccessible
4. Review error logs for specific failure reasons

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL` | No | None | Google Doc URL or ID containing extended system prompt |
| `GDRIVE_CLIENT_ID` | Yes* | None | Google OAuth client ID (*required if using extended prompt) |
| `GDRIVE_CLIENT_SECRET` | Yes* | None | Google OAuth client secret (*required if using extended prompt) |
| `GEMINI_API_KEY` | Yes | None | Gemini API key for the underlying model |

### Agent Parameters

When creating a ReleaseManager instance:

```python
manager = ReleaseManager(
    temperature=0.7,      # Optional: Model temperature (0.0-2.0)
    max_tokens=4096,      # Optional: Maximum response tokens
)
```

### Toolkit Configuration

The Release Manager automatically detects and configures toolkits:

- **GoogleDriveConfig**: Required for extended system prompt feature
- **JiraConfig**: Optional, for Jira integration

See individual toolkit documentation for configuration details.

## Development

### Adding New Toolkits

1. Create toolkit config class extending `BaseToolkitConfig`
2. Add to `self.toolkit_configs` list in `ReleaseManager.__init__()`
3. Implement required methods: `is_configured()`, `get_toolkit()`, `get_agent_instructions()`

### Modifying System Prompt Logic

Key methods:

- `_fetch_extended_system_prompt(user_id)`: Fetches and caches extended prompt
- `_invalidate_system_prompt(user_id)`: Clears cached prompt for a user
- `_get_or_create_agent(user_id)`: Composes full system prompt and creates agent

### Testing

Run tests with:

```bash
nox -s test

# Specific tests
uv run pytest tests/test_release_manager.py -v
```

## Future Enhancements

- [ ] Manual cache refresh API endpoint
- [ ] Per-user custom prompt documents (override global default)
- [ ] Prompt template variables (e.g., `{user_name}`, `{team}`)
- [ ] Prompt versioning and A/B testing
- [ ] Prompt analytics and effectiveness tracking


### Release Manager System Prompt Architecture

The Release Manager uses a **dual-prompt architecture** that separates stable agent capabilities from dynamic operational context:

**Embedded System Prompt** (in `release_manager.py` lines 152-181):
- **What it contains:** Core identity, responsibilities, available tools, behavioral guidelines
- **Purpose:** "Who you are and what you can do"
- **Characteristics:** Stable, version-controlled, changes rarely
- **Examples:**
  - Identity as RHDH Release Manager
  - Core responsibilities (Y-stream, Z-stream management)
  - Available tools (Jira, Google Drive, GitHub)
  - Output and behavioral guidelines

**External System Prompt** (fetched from Google Drive):
- **What it contains:** Current release context, processes, examples, Jira query templates
- **Purpose:** "What you're currently working on and how to do it"
- **Characteristics:** Frequently updated, context-specific, operational details
- **Examples:**
  - Active release versions and dates (1.7.0, 1.8.0)
  - Jira query templates for tracking features, blockers, CVEs
  - Release Manager Update format examples
  - Communication guidelines and key resource links

**Template Location:**
- `docs/release_manager_system_prompt.md` - Recommended content structure for the external prompt
- Copy this content to a Google Doc and configure via `RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL`

**Design Benefits:**
- **Code changes** for capability updates (new tools, behavior changes)
- **Doc updates** for operational changes (new releases, updated processes)
- Easy testing of prompt changes without code deployment
- Clear separation of concerns between stable identity and dynamic context
