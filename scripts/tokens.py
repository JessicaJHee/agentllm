#!/usr/bin/env python3
"""CLI tool for managing tokens in AgentLLM database.

This script provides commands to view, inspect, and manage OAuth tokens
and API credentials stored in the AgentLLM database.

Usage:
    python scripts/tokens.py list              # List all tokens
    python scripts/tokens.py users             # List user IDs
    python scripts/tokens.py first-user        # Get first configured user
    python scripts/tokens.py details USER_ID   # Show token details
    python scripts/tokens.py delete USER_ID    # Delete user tokens
"""

import sys
from datetime import datetime
from pathlib import Path

import click
from agno.db.sqlite import SqliteDb
from dotenv import load_dotenv

# Load environment variables from .env.secrets (for encryption key)
repo_root = Path(__file__).parent.parent
env_secrets = repo_root / ".env.secrets"
if env_secrets.exists():
    load_dotenv(env_secrets)

# Add src to path so we can import agentllm
sys.path.insert(0, str(repo_root / "src"))

from agentllm.db.token_storage import TokenStorage  # noqa: E402


def get_db_and_storage(db_path: str = "tmp/agent-data/agno_sessions.db") -> tuple[SqliteDb, TokenStorage]:
    """Get database and token storage instances.

    Args:
        db_path: Path to the database file (defaults to containerized database path)

    Returns:
        Tuple of (SqliteDb, TokenStorage)

    Raises:
        click.ClickException: If database doesn't exist
    """
    db_file = Path(db_path)
    if not db_file.exists():
        raise click.ClickException(
            f"Database not found: {db_path}\nRun the development stack first: just dev\nOr for local proxy mode: nox -s proxy"
        )

    db = SqliteDb(db_file=str(db_file))
    storage = TokenStorage(agno_db=db)
    return db, storage


@click.group()
def cli():
    """AgentLLM Token Management CLI."""
    pass


@cli.command()
@click.option("--db", default="tmp/agent-data/agno_sessions.db", help="Path to database file")
def list(db: str):
    """List all users and their tokens."""
    _, storage = get_db_and_storage(db)

    click.echo("=" * 80)
    click.echo(f"🔐 Token Storage Summary - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    click.echo("=" * 80)
    click.echo()

    # Get all tokens using the TokenStorage API
    session = storage.Session()
    try:
        # Jira Tokens
        click.echo("📋 JIRA TOKENS")
        click.echo("─" * 80)

        from agentllm.db.token_storage import JiraToken

        jira_tokens = session.query(JiraToken).order_by(JiraToken.updated_at.desc()).all()

        if jira_tokens:
            # Header
            click.echo(f"{'User ID':<40} {'Server URL':<40} {'Username':<20} {'Last Updated':<25}")
            click.echo(f"{'-' * 40} {'-' * 40} {'-' * 20} {'-' * 25}")
            for token in jira_tokens:
                username = token.username or ""
                updated = token.updated_at.strftime("%Y-%m-%d %H:%M:%S") if token.updated_at else "N/A"
                click.echo(f"{token.user_id:<40} {token.server_url:<40} {username:<20} {updated:<25}")
        else:
            click.echo("  (no tokens)")

        click.echo()
        click.echo(f"Total: {len(jira_tokens)} user(s)")
        click.echo()

        # Google Drive Tokens
        click.echo("📁 GOOGLE DRIVE TOKENS")
        click.echo("─" * 80)

        from agentllm.db.token_storage import GoogleDriveToken

        gdrive_tokens = session.query(GoogleDriveToken).order_by(GoogleDriveToken.updated_at.desc()).all()

        if gdrive_tokens:
            # Header
            click.echo(f"{'User ID':<40} {'Token Expiry':<25} {'Last Updated':<25}")
            click.echo(f"{'-' * 40} {'-' * 25} {'-' * 25}")
            for token in gdrive_tokens:
                expiry = token.expiry.strftime("%Y-%m-%d %H:%M:%S") if token.expiry else "N/A"
                updated = token.updated_at.strftime("%Y-%m-%d %H:%M:%S") if token.updated_at else "N/A"
                click.echo(f"{token.user_id:<40} {expiry:<25} {updated:<25}")
        else:
            click.echo("  (no tokens)")

        click.echo()
        click.echo(f"Total: {len(gdrive_tokens)} user(s)")
        click.echo()

        # GitHub Tokens
        click.echo("🐙 GITHUB TOKENS")
        click.echo("─" * 80)

        from agentllm.db.token_storage import GitHubToken

        github_tokens = session.query(GitHubToken).order_by(GitHubToken.updated_at.desc()).all()

        if github_tokens:
            # Header
            click.echo(f"{'User ID':<40} {'Server URL':<40} {'Username':<20} {'Last Updated':<25}")
            click.echo(f"{'-' * 40} {'-' * 40} {'-' * 20} {'-' * 25}")
            for token in github_tokens:
                username = token.username or ""
                updated = token.updated_at.strftime("%Y-%m-%d %H:%M:%S") if token.updated_at else "N/A"
                click.echo(f"{token.user_id:<40} {token.server_url:<40} {username:<20} {updated:<25}")
        else:
            click.echo("  (no tokens)")

        click.echo()
        click.echo(f"Total: {len(github_tokens)} user(s)")
        click.echo()

        # RHCP Tokens
        click.echo("🔴 RED HAT CUSTOMER PORTAL TOKENS")
        click.echo("─" * 80)

        from agentllm.db.token_storage import RHCPToken

        rhcp_tokens = session.query(RHCPToken).order_by(RHCPToken.updated_at.desc()).all()

        if rhcp_tokens:
            # Header
            click.echo(f"{'User ID':<40} {'Last Updated':<25}")
            click.echo(f"{'-' * 40} {'-' * 25}")
            for token in rhcp_tokens:
                updated = token.updated_at.strftime("%Y-%m-%d %H:%M:%S") if token.updated_at else "N/A"
                click.echo(f"{token.user_id:<40} {updated:<25}")
        else:
            click.echo("  (no tokens)")

        click.echo()
        click.echo(f"Total: {len(rhcp_tokens)} user(s)")
        click.echo()

        # Summary
        click.echo("=" * 80)
        click.echo("📊 SUMMARY")
        click.echo("─" * 80)
        click.echo(f"  Jira:         {len(jira_tokens)} user(s)")
        click.echo(f"  Google Drive: {len(gdrive_tokens)} user(s)")
        click.echo(f"  GitHub:       {len(github_tokens)} user(s)")
        click.echo(f"  RHCP:         {len(rhcp_tokens)} user(s)")
        click.echo("=" * 80)

    finally:
        session.close()


@cli.command()
@click.option("--db", default="tmp/agent-data/agno_sessions.db", help="Path to database file")
def users(db: str):
    """List all unique user IDs."""
    _, storage = get_db_and_storage(db)

    session = storage.Session()
    try:
        from agentllm.db.token_storage import GitHubToken, GoogleDriveToken, JiraToken, RHCPToken

        # Get unique user IDs from all token tables
        user_ids = set()

        for token in session.query(JiraToken).all():
            user_ids.add(token.user_id)

        for token in session.query(GoogleDriveToken).all():
            user_ids.add(token.user_id)

        for token in session.query(GitHubToken).all():
            user_ids.add(token.user_id)

        for token in session.query(RHCPToken).all():
            user_ids.add(token.user_id)

        click.echo("All configured user IDs:")
        for user_id in sorted(user_ids):
            click.echo(user_id)

    finally:
        session.close()


@cli.command()
@click.option("--db", default="tmp/agent-data/agno_sessions.db", help="Path to database file")
def first_user(db: str):
    """Get the first configured user ID (with both Jira and Google Drive tokens).

    Useful for test fixtures and automation.
    Prints only the user ID to stdout (no extra output).
    """
    _, storage = get_db_and_storage(db)

    session = storage.Session()
    try:
        from agentllm.db.token_storage import GoogleDriveToken, JiraToken

        # Find users with both Jira and Google Drive tokens (Release Manager requirement)
        jira_users = {token.user_id for token in session.query(JiraToken).all()}
        gdrive_users = {token.user_id for token in session.query(GoogleDriveToken).all()}

        # Users with both tokens
        both_tokens = jira_users & gdrive_users

        if both_tokens:
            # Get the most recently updated one
            most_recent = session.query(JiraToken).filter(JiraToken.user_id.in_(both_tokens)).order_by(JiraToken.updated_at.desc()).first()
            if most_recent:
                click.echo(most_recent.user_id)
                return

        # Fallback: any user with any token
        all_users = jira_users | gdrive_users
        if all_users:
            user_id = sorted(all_users)[0]
            click.echo(user_id)
            return

        # No users found
        sys.exit(1)

    finally:
        session.close()


@cli.command()
@click.argument("user_id")
@click.option("--db", default="tmp/agent-data/agno_sessions.db", help="Path to database file")
def details(user_id: str, db: str):
    """Show detailed token information for a specific user."""
    _, storage = get_db_and_storage(db)

    click.echo("=" * 80)
    click.echo(f"🔐 Token Details for User: {user_id}")
    click.echo("=" * 80)
    click.echo()

    session = storage.Session()
    try:
        from agentllm.db.token_storage import GitHubToken, GoogleDriveToken, JiraToken, RHCPToken

        # Jira Token
        click.echo("📋 Jira Token:")
        jira_token = session.query(JiraToken).filter_by(user_id=user_id).first()
        if jira_token:
            click.echo(f"  User ID:      {jira_token.user_id}")
            click.echo(f"  Server URL:   {jira_token.server_url}")
            click.echo(f"  Username:     {jira_token.username or 'N/A'}")
            click.echo(f"  Created:      {jira_token.created_at.strftime('%Y-%m-%d %H:%M:%S') if jira_token.created_at else 'N/A'}")
            click.echo(f"  Updated:      {jira_token.updated_at.strftime('%Y-%m-%d %H:%M:%S') if jira_token.updated_at else 'N/A'}")
        else:
            click.echo("  (not configured)")
        click.echo()

        # Google Drive Token
        click.echo("📁 Google Drive Token:")
        gdrive_token = session.query(GoogleDriveToken).filter_by(user_id=user_id).first()
        if gdrive_token:
            click.echo(f"  User ID:      {gdrive_token.user_id}")
            click.echo(f"  Expires:      {gdrive_token.expiry.strftime('%Y-%m-%d %H:%M:%S') if gdrive_token.expiry else 'N/A'}")
            click.echo(f"  Created:      {gdrive_token.created_at.strftime('%Y-%m-%d %H:%M:%S') if gdrive_token.created_at else 'N/A'}")
            click.echo(f"  Updated:      {gdrive_token.updated_at.strftime('%Y-%m-%d %H:%M:%S') if gdrive_token.updated_at else 'N/A'}")
        else:
            click.echo("  (not configured)")
        click.echo()

        # GitHub Token
        click.echo("🐙 GitHub Token:")
        github_token = session.query(GitHubToken).filter_by(user_id=user_id).first()
        if github_token:
            click.echo(f"  User ID:      {github_token.user_id}")
            click.echo(f"  Server URL:   {github_token.server_url}")
            click.echo(f"  Username:     {github_token.username or 'N/A'}")
            click.echo(f"  Created:      {github_token.created_at.strftime('%Y-%m-%d %H:%M:%S') if github_token.created_at else 'N/A'}")
            click.echo(f"  Updated:      {github_token.updated_at.strftime('%Y-%m-%d %H:%M:%S') if github_token.updated_at else 'N/A'}")
        else:
            click.echo("  (not configured)")
        click.echo()

        # RHCP Token
        click.echo("🔴 RHCP Token:")
        rhcp_token = session.query(RHCPToken).filter_by(user_id=user_id).first()
        if rhcp_token:
            click.echo(f"  User ID:      {rhcp_token.user_id}")
            click.echo(f"  Created:      {rhcp_token.created_at.strftime('%Y-%m-%d %H:%M:%S') if rhcp_token.created_at else 'N/A'}")
            click.echo(f"  Updated:      {rhcp_token.updated_at.strftime('%Y-%m-%d %H:%M:%S') if rhcp_token.updated_at else 'N/A'}")
        else:
            click.echo("  (not configured)")
        click.echo()

    finally:
        session.close()


@cli.command()
@click.argument("user_id")
@click.option("--db", default="tmp/agent-data/agno_sessions.db", help="Path to database file")
@click.confirmation_option(prompt="Are you sure you want to delete all tokens for this user?")
def delete(user_id: str, db: str):
    """Delete all tokens for a specific user (requires confirmation)."""
    _, storage = get_db_and_storage(db)

    session = storage.Session()
    try:
        from agentllm.db.token_storage import GitHubToken, GoogleDriveToken, JiraToken, RHCPToken

        # Delete tokens from all tables
        jira_deleted = session.query(JiraToken).filter_by(user_id=user_id).delete()
        gdrive_deleted = session.query(GoogleDriveToken).filter_by(user_id=user_id).delete()
        github_deleted = session.query(GitHubToken).filter_by(user_id=user_id).delete()
        rhcp_deleted = session.query(RHCPToken).filter_by(user_id=user_id).delete()

        session.commit()

        total_deleted = jira_deleted + gdrive_deleted + github_deleted + rhcp_deleted

        if total_deleted > 0:
            click.echo(f"✅ Deleted {total_deleted} token(s) for user: {user_id}")
            if jira_deleted:
                click.echo(f"   - Jira: {jira_deleted}")
            if gdrive_deleted:
                click.echo(f"   - Google Drive: {gdrive_deleted}")
            if github_deleted:
                click.echo(f"   - GitHub: {github_deleted}")
            if rhcp_deleted:
                click.echo(f"   - RHCP: {rhcp_deleted}")
        else:
            click.echo(f"⚠️  No tokens found for user: {user_id}")

    except Exception as e:
        session.rollback()
        raise click.ClickException(f"Failed to delete tokens: {e}") from e
    finally:
        session.close()


if __name__ == "__main__":
    cli()
