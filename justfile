# AgentLLM Development Utilities
# Requires: just (https://just.systems/)

# Default recipe - show available commands
default:
    @just --list

# List all users and their tokens from the session database
tokens:
    uv run python scripts/tokens.py list

# List only user IDs (useful for scripts)
users:
    uv run python scripts/tokens.py users

# Get the first configured user ID (useful for test fixtures)
first-user:
    uv run python scripts/tokens.py first-user

# Show detailed token information for a specific user
token-details USER_ID:
    uv run python scripts/tokens.py details {{ USER_ID }}

# Delete all tokens for a specific user (use with caution!)
delete-user-tokens USER_ID:
    uv run python scripts/tokens.py delete {{ USER_ID }}

# Clean up all test database files
clean-test-dbs:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "🧹 Cleaning up test databases..."

    find tmp -name "test_*.db" -type f -delete 2>/dev/null || true

    echo "✅ Test databases cleaned"
