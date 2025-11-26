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
#     "rich>=13.0.0",
# ]
# ///
"""Example script demonstrating how to use RHAITools to fetch and display RHAI release information.

This script shows how to:
1. Get Google Drive OAuth credentials from token storage
2. Instantiate RHAITools
3. Fetch release information from Google Sheets
4. Display the results in a formatted table

Requirements:
- AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET environment variable
- AGENTLLM_DATA_DIR environment variable (default: tmp/)
- User must have Google Drive credentials stored in token database

Usage:
    uv run examples/rhai_releases_example.py <user_id>
    # OR
    python examples/rhai_releases_example.py <user_id>

    user_id: The user identifier to fetch Google Drive credentials for
             (must have authorized Google Drive through the agent)

Example:
    uv run examples/rhai_releases_example.py demo-user
"""

import argparse
import os
import sys
from pathlib import Path

# Add src directory to path to allow imports
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from loguru import logger  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402

from agentllm.db.token_storage import TokenStorage  # noqa: E402
from agentllm.tools.rhai_toolkit import RHAITools  # noqa: E402

# Initialize rich console
console = Console()


def main():
    """Main function to fetch and display RHAI releases."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Fetch and display RHAI release information using RHAITools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s demo-user
  %(prog)s user@example.com

Note: The user must have authorized Google Drive through the agent first.
      This example uses credentials stored in the token database.
        """,
    )
    parser.add_argument(
        "user_id",
        help="User identifier to fetch Google Drive credentials for",
    )
    args = parser.parse_args()

    # Print header
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]🚀 RHAI Releases Example[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print(f"[bold]User ID:[/bold] {args.user_id}")
    console.print()

    # Check for release sheet URL
    sheet_url = os.getenv("AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET")
    if not sheet_url:
        console.print(
            "[bold red]❌ Error:[/bold red] Missing environment variable [cyan]AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET[/cyan]"
        )
        console.print("   This should be set to the URL of the Google Sheets document containing RHAI releases.")
        sys.exit(1)

    console.print(f"[bold]Release sheet:[/bold] [dim]{sheet_url}[/dim]")

    # Set up token storage
    data_dir = os.getenv("AGENTLLM_DATA_DIR", "tmp/")
    token_db_path = os.path.join(data_dir, "agno_sessions.db")

    if not Path(token_db_path).exists():
        console.print(f"[bold red]❌ Error:[/bold red] Token database not found: [cyan]{token_db_path}[/cyan]")
        console.print("   You need to authorize Google Drive through the agent first.")
        console.print("   Start the agent and interact with it to trigger Google Drive authorization.")
        sys.exit(1)

    console.print(f"[bold]Token database:[/bold] [dim]{token_db_path}[/dim]")
    console.print()

    try:
        # Initialize token storage
        token_storage = TokenStorage(db_file=token_db_path)

        # Get Google Drive credentials from token storage
        with console.status(f"[bold cyan]🔑 Fetching Google Drive credentials for user: {args.user_id}[/bold cyan]"):
            credentials = token_storage.get_token("gdrive", args.user_id)

        if not credentials:
            console.print(f"[bold red]❌ Error:[/bold red] No Google Drive credentials found for user: [cyan]{args.user_id}[/cyan]")
            console.print("\n[yellow]The user needs to authorize Google Drive first.[/yellow]")
            console.print("You can do this by:")
            console.print("  1. Starting the agent: [cyan]nox -s proxy[/cyan]")
            console.print("  2. Interacting with [cyan]agno/release-manager[/cyan] or [cyan]agno/demo-agent[/cyan] through Open WebUI")
            console.print("  3. Following the OAuth authorization flow when prompted")

            available_users = token_storage.list_users_with_gdrive_tokens()
            if available_users:
                console.print("\n[bold]Available users with Google Drive credentials:[/bold]")
                for user in available_users:
                    console.print(f"  • {user}")
            sys.exit(1)

        console.print("✅ [green]Google Drive credentials loaded successfully[/green]")
        console.print()

        # Create RHAITools instance and fetch releases
        with console.status("[bold cyan]🛠️  Creating RHAITools instance...[/bold cyan]"):
            rhai_tools = RHAITools(credentials=credentials)

        with console.status("[bold cyan]📥 Fetching RHAI releases...[/bold cyan]"):
            releases = rhai_tools.get_releases()

        # Display summary table
        console.print()
        console.print(
            Panel.fit(
                f"[bold green]🎯 Found {len(releases)} RHAI Release(s)[/bold green]",
                border_style="green",
            )
        )
        console.print()

        if releases:
            # Create rich table
            table = Table(
                title="[bold cyan]RED HAT AI (RHAI) RELEASES[/bold cyan]",
                show_header=True,
                header_style="bold magenta",
                border_style="cyan",
                title_style="bold cyan",
            )
            table.add_column("Release", style="cyan", no_wrap=True)
            table.add_column("Details", style="white")
            table.add_column("Release Date", style="yellow", no_wrap=True)

            for release in releases:
                table.add_row(
                    release.release,
                    release.details,
                    str(release.release_date),
                )

            console.print(table)
            console.print()

            # Display detailed information
            console.print(
                Panel(
                    "[bold]📋 DETAILED RELEASE INFORMATION[/bold]",
                    border_style="blue",
                )
            )
            console.print()

            for i, release in enumerate(releases, 1):
                console.print(f"[bold cyan]{i}. {release.release}[/bold cyan]")
                console.print(f"   [bold]Details:[/bold] {release.details}")
                console.print(f"   [bold]Release Date:[/bold] [yellow]{release.release_date}[/yellow]")
                console.print()

        console.print("[bold green]✅ Example completed successfully![/bold green]")
        console.print()

    except Exception as e:
        console.print()
        console.print(
            Panel(
                f"[bold red]❌ Error fetching releases[/bold red]\n\n[yellow]{type(e).__name__}:[/yellow] {e}",
                border_style="red",
                title="[bold red]Error[/bold red]",
            )
        )
        logger.exception("Error details:")
        sys.exit(1)


if __name__ == "__main__":
    main()
