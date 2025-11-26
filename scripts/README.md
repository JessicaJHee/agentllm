# AgentLLM Scripts

Utility scripts for AgentLLM development and administration.

## Token Management (`tokens.py`)

CLI tool for viewing and managing OAuth tokens and API credentials stored in the AgentLLM database.

### Usage

Via `just` (recommended):

```bash
# List all tokens
just tokens

# List user IDs
just users

# Get first configured user (useful for tests)
just first-user

# Show details for a specific user
just token-details USER_ID

# Delete all tokens for a user (with confirmation)
just delete-user-tokens USER_ID
```

Direct usage:

```bash
# List all tokens
uv run python scripts/tokens.py list

# Get help
uv run python scripts/tokens.py --help

# Show help for a specific command
uv run python scripts/tokens.py list --help
```

### Features

- **Database Abstraction**: Uses the actual `TokenStorage` class and SQLAlchemy models
- **Type Safe**: Full IDE support and type checking
- **Rich Output**: Beautiful formatted tables and summaries
- **Error Handling**: Clear error messages if database doesn't exist
- **Confirmation Prompts**: Safe delete operations with user confirmation

### Examples

**List all tokens:**

```bash
$ just tokens
================================================================================
🔐 Token Storage Summary - 2025-11-25 18:13:53
================================================================================

📋 JIRA TOKENS
────────────────────────────────────────────────────────────────────────────────
User ID                                  Server URL                               Username             Last Updated
---------------------------------------- ---------------------------------------- -------------------- -------------------------
c7862325-72b9-46e4-9de1-2ba5c4086406     https://issues.redhat.com                                     2025-11-11 15:24:24

Total: 1 user(s)
...
```

**Get first configured user:**

```bash
$ just first-user
c7862325-72b9-46e4-9de1-2ba5c4086406
```

**Show token details:**

```bash
$ just token-details c7862325-72b9-46e4-9de1-2ba5c4086406
================================================================================
🔐 Token Details for User: c7862325-72b9-46e4-9de1-2ba5c4086406
================================================================================

📋 Jira Token:
  User ID:      c7862325-72b9-46e4-9de1-2ba5c4086406
  Server URL:   https://issues.redhat.com
  Username:     N/A
  Created:      2025-11-11 15:24:24
  Updated:      2025-11-11 15:24:24
...
```

### Use in Tests

The `first-user` command is specifically designed for test fixtures:

```python
def get_configured_user_id() -> str | None:
    """Get the first user ID with both Jira and Google Drive tokens configured."""
    try:
        result = subprocess.run(
            ["just", "first-user"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() if result.stdout.strip() else None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
```

### Database Location

By default, the script uses `tmp/agent-data/agno_sessions.db`. You can override this with the `--db` flag:

```bash
uv run python scripts/tokens.py list --db /path/to/custom.db
```

### Adding New Token Types

To add support for a new token type:

1. Add the SQLAlchemy model to `src/agentllm/db/token_storage.py`
2. Update the `list()` and `details()` commands in `scripts/tokens.py`
3. Import the new model and add queries for it

Example:

```python
# In list() command
from agentllm.db.token_storage import NewTokenType

new_tokens = session.query(NewTokenType).order_by(NewTokenType.updated_at.desc()).all()
# ... display logic
```

No changes needed to the `justfile` - it just delegates to the Python script!
