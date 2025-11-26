# AgentLLM Examples

This directory contains example scripts demonstrating how to use AgentLLM's tools and components directly, without going through the LiteLLM proxy.

All examples are **UV scripts** with embedded dependency specifications using [PEP 723](https://peps.python.org/pep-0723/) inline script metadata. This means you can run them directly with `uv run` without any prior installation or virtual environment setup.

## UV Scripts

Each example includes a `# /// script` section at the top that declares its dependencies:

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "agno>=2.2.10",
#     "jira>=3.0.0",
#     "loguru>=0.7.0",
#     # ... more dependencies
# ]
# ///
```

**Benefits:**
- ✅ **No manual installation**: `uv run` automatically installs dependencies in an isolated environment
- ✅ **Reproducible**: Dependencies are version-pinned in the script itself
- ✅ **Portable**: Share scripts without worrying about environment setup
- ✅ **Fast**: UV caches dependencies for quick subsequent runs

**Usage:**
```bash
# Just run with uv - dependencies are auto-installed
uv run examples/rhai_releases_example.py <args>

# Or make executable and run directly
chmod +x examples/rhai_releases_example.py
./examples/rhai_releases_example.py <args>
```

## Available Examples

### RHAI Releases Example

**File:** `rhai_releases_example.py`

**Description:** Demonstrates how to use RHAITools to fetch and display Red Hat AI (RHAI) release information from Google Sheets.

**Features:**
- Uses token storage to retrieve Google Drive credentials
- Fetches release data from configured Google Sheets
- Beautiful terminal UI with Rich library (colored output, progress indicators, tables)
- Displays results in formatted tables with syntax highlighting
- Shows detailed release information with interactive panels

**Requirements:**
- `AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET` environment variable must be set
- `AGENTLLM_DATA_DIR` environment variable (default: `tmp/`)
- User must have Google Drive credentials stored in token database

**Usage:**

```bash
# Using uv run (recommended - auto-installs dependencies)
uv run examples/rhai_releases_example.py <user_id>

# Using nox session
nox -s example_rhai_releases -- <user_id>

# Direct Python execution (requires manual dependency installation)
python examples/rhai_releases_example.py <user_id>

# Make executable and run directly
chmod +x examples/rhai_releases_example.py
./examples/rhai_releases_example.py <user_id>
```

**Examples:**

```bash
# With a UUID user ID
uv run examples/rhai_releases_example.py bc1861ec-afe8-459c-bfb5-8c3ab866aee4

# With an email user ID
uv run examples/rhai_releases_example.py user@example.com

# Using nox
nox -s example_rhai_releases -- bc1861ec-afe8-459c-bfb5-8c3ab866aee4
```

**Prerequisites:**

1. The user must have authorized Google Drive through the agent first
2. Check available users:
   ```bash
   uv run python -c "
   import sys
   sys.path.insert(0, 'src')
   from agentllm.db.token_storage import TokenStorage
   ts = TokenStorage(db_file='tmp/agent-data/agno_sessions.db')
   print('Available users:', ts.list_users_with_gdrive_tokens())
   "
   ```

**Output:**

The script produces beautifully formatted terminal output using the Rich library:

```
╭────────────────────────────╮
│ 🚀 RHAI Releases Example  │
╰────────────────────────────╯
User ID: demo-user

Release sheet: https://docs.google.com/document/d/...
Token database: tmp/agent-data/agno_sessions.db

🔑 Fetching Google Drive credentials for user: demo-user
✅ Google Drive credentials loaded successfully

🛠️  Creating RHAITools instance...
📥 Fetching RHAI releases...

╭──────────────────────────────────╮
│ 🎯 Found 8 RHAI Release(s)      │
╰──────────────────────────────────╯

         RED HAT AI (RHAI) RELEASES
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┓
┃ Release      ┃ Details         ┃ Planned Release    ┃
┃              ┃                 ┃ Date               ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━┩
│ RHAIIS-3.2.4 │ RHAIIS 3.2.4... │ Thu Nov-13-2025    │
│ rhelai-3.0   │ rhelai-3.0 GA...│ Thu Nov-13-2025    │
│ rhoai-3.0    │ 3.0 RHOAI GA    │ Thu Nov-13-2025    │
│ ...          │ ...             │ ...                │
└──────────────┴─────────────────┴────────────────────┘

╭─────────────────────────────────────────╮
│ 📋 DETAILED RELEASE INFORMATION        │
╰─────────────────────────────────────────╯

1. RHAIIS-3.2.4
   Details: RHAIIS 3.2.4 Release (AIPCC)
   Planned Release Date: Thu Nov-13-2025

2. rhelai-3.0
   Details: rhelai-3.0 GA (Nvidia support only)
   Planned Release Date: Thu Nov-13-2025

...

✅ Example completed successfully!
```

**Features in Output:**
- 🎨 **Colored syntax highlighting** - Different colors for different data types
- 📊 **Rich tables** - Beautiful Unicode box-drawing characters
- 🔄 **Progress indicators** - Spinners while fetching data
- 📦 **Panels** - Grouped information with borders
- ⚡ **Real-time updates** - Status messages during execution

---

### Token Storage Example

**File:** `token_storage_example.py`

**Description:** Demonstrates how to use TokenStorage for managing Jira and Google Drive credentials.

**Features:**
- Store and retrieve Jira API tokens
- Store and retrieve Google Drive OAuth credentials
- List users with stored credentials
- Initialize toolkits with database-backed authentication

**Usage:**

```bash
# Using uv run (recommended - auto-installs dependencies)
uv run examples/token_storage_example.py

# Direct execution
python examples/token_storage_example.py

# Make executable and run directly
chmod +x examples/token_storage_example.py
./examples/token_storage_example.py
```

**Note:** The example includes commented-out function calls. Uncomment the ones you want to test.

See the file for detailed usage examples and implementation details.

## Creating Your Own Examples

When creating new examples:

1. **Start with UV script metadata:**
   ```python
   #!/usr/bin/env -S uv run
   # /// script
   # requires-python = ">=3.11"
   # dependencies = [
   #     "agno>=2.2.10",
   #     "jira>=3.0.0",
   #     "loguru>=0.7.0",
   #     "sqlalchemy>=2.0.0",
   #     "google-auth-oauthlib>=1.0.0",
   #     "google-api-python-client>=2.0.0",
   #     "html-to-markdown>=1.0.0",
   #     "rich>=13.0.0",  # For beautiful terminal output
   # ]
   # ///
   """Your example description here."""
   ```

2. **Add src to path:**
   ```python
   import sys
   from pathlib import Path
   src_path = Path(__file__).parent.parent / "src"
   sys.path.insert(0, str(src_path))
   ```

3. **Use TokenStorage for credentials:**
   ```python
   from agentllm.db.token_storage import TokenStorage
   token_storage = TokenStorage(db_file="tmp/agent-data/agno_sessions.db")
   credentials = token_storage.get_gdrive_credentials(user_id)
   ```

4. **Make it executable:**
   ```bash
   chmod +x examples/my_example.py
   ```

5. **(Optional) Add a nox session for convenience:**
   ```python
   @nox.session(venv_backend="none")
   def example_my_feature(session):
       """Description of your example."""
       session.run("uv", "run", "examples/my_example.py", external=True)
   ```

6. **Document your example in this README**

**Why use UV scripts?**
- Users can run your example without installing the project
- Dependencies are declared inline and auto-installed
- No need to maintain separate requirements files
- Scripts are self-contained and portable

## Troubleshooting

### "Token database not found"

The token database is created when users first interact with the agent. To create it:

```bash
# Start the proxy
nox -s proxy

# In another terminal, make a test request or use Open WebUI
# The database will be created automatically
```

### "No Google Drive credentials found"

Users need to authorize Google Drive through the agent first:

1. Start the development environment: `nox -s dev_local_proxy`
2. Access Open WebUI at http://localhost:8080
3. Select `agno/release-manager` or `agno/demo-agent`
4. Follow the OAuth authorization flow when prompted
5. Credentials will be stored in the token database

### "Missing environment variable"

Check your `.env` or `.envrc` file has the required variables:

```bash
AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET=https://docs.google.com/spreadsheets/d/...
AGENTLLM_DATA_DIR=tmp/
```

## Related Documentation

- [Main README](../README.md) - Project overview
- [CLAUDE.md](../CLAUDE.md) - Development guide and architecture
- [Token Storage](../src/agentllm/db/token_storage.py) - Database-backed credential storage
- [RHAITools](../src/agentllm/tools/rhai_toolkit.py) - RHAI release data toolkit
