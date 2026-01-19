#!/usr/bin/env python3
"""Automated Jira triage with auto-apply.

This script runs Jira Triager in headless mode for CI/CD automation.
It processes triage recommendations and auto-applies all changes.

Usage:
    # Dry-run (preview only)
    python scripts/auto_triage.py --dry-run

    # Apply all recommendations
    python scripts/auto_triage.py --apply

    # Custom JQL filter
    python scripts/auto_triage.py --apply --jql "project=RHIDP AND status='To Do'"

    # JSON output for CI/CD
    python scripts/auto_triage.py --apply --json-output

Exit Codes:
    0 - Success (all applied successfully)
    1 - Failures (some updates failed)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger

from agno.db.sqlite import SqliteDb

# Import toolkit configs to register token types with global registry
from agentllm.agents.toolkit_configs.jira_config import JiraConfig  # noqa: F401

# Constants
AUTOMATION_USER_ID = "jira-triager-bot"
DB_PATH = "tmp/agent-data/agno_sessions.db"
# Config file: use env var, or "config/rhdh-teams.json" (CI), or fallback to "tmp/rhdh-teams.json" (local dev)
CONFIG_FILE_PATH = os.getenv("JIRA_TRIAGER_CONFIG_FILE") or (
    "config/rhdh-teams.json" if os.path.exists("config/rhdh-teams.json") else "tmp/rhdh-teams.json"
)
DEFAULT_JQL_FILTER = (
    'project in ("Red Hat Internal Developer Platform", "RHDH Support", "Red Hat Developer Hub Bugs") '
    "AND status != closed "
    "AND (Team is EMPTY OR component is EMPTY) "
    'AND issuetype not in (Sub-task, Feature, "Feature Request", Outcome) '
    "ORDER BY created DESC, priority DESC"
)

# Signal automation mode to configurator (disables Google Drive requirement)
# This must be set before importing/creating the JiraTriager agent
if not os.environ.get("JIRA_TRIAGER_CONFIG_FILE"):
    os.environ["JIRA_TRIAGER_CONFIG_FILE"] = CONFIG_FILE_PATH


def parse_triage_table(response_text: str) -> list[dict]:
    """Parse triage recommendations from agent response.

    Looks for markdown table with format:
    | Ticket | Summary | Field | Current | Recommended | Confidence | Action |

    Args:
        response_text: Full agent response text

    Returns:
        List of recommendation dictionaries
    """
    recommendations = []

    # Find table in response (look for header row)
    table_pattern = r"\| Ticket \| Summary \| Field \| Current \| Recommended \| Confidence \| Action \|"
    match = re.search(table_pattern, response_text)

    if not match:
        logger.warning("No triage table found in response")
        return recommendations

    # Extract table section
    table_start = match.start()
    table_text = response_text[table_start:]

    # Parse each data row (skip header and separator)
    lines = table_text.split("\n")
    current_ticket = None

    for line in lines[2:]:  # Skip header and separator
        if not line.strip() or not line.startswith("|"):
            break

        # Parse columns
        cols = [col.strip() for col in line.split("|")[1:-1]]  # Remove empty first/last

        if len(cols) < 7:
            continue

        ticket, _summary, field, current, recommended, confidence_str, action = cols

        # If ticket is empty, use previous ticket (multi-row format)
        if ticket:
            current_ticket = ticket
        elif current_ticket:
            ticket = current_ticket
        else:
            continue

        # Skip if action is not NEW (skip APPEND and SKIP)
        if action.upper() != "NEW":
            logger.debug(f"Skipping {ticket} {field} (action: {action})")
            continue

        # Parse confidence percentage
        confidence_match = re.search(r"(\d+)%", confidence_str)
        confidence = int(confidence_match.group(1)) if confidence_match else 0

        # Build recommendation dict
        rec = {
            "ticket": ticket,
            "field": field.lower(),
            "current": current,
            "recommended": recommended,
            "confidence": confidence,
            "action": action,
        }

        recommendations.append(rec)

    unique_issues = len(set(rec["ticket"] for rec in recommendations))
    logger.info(f"Parsed {len(recommendations)} recommendations for {unique_issues} issues from table")
    return recommendations


def classify_recommendations(recommendations: list[dict], threshold: int) -> dict:
    """Classify recommendations (applies all regardless of threshold).

    Args:
        recommendations: List of recommendation dictionaries
        threshold: Unused (kept for backward compatibility)

    Returns:
        Dictionary with 'auto_apply' containing all items
    """
    unique_count = len(set(rec["ticket"] for rec in recommendations))
    logger.info(
        f"Will apply all {len(recommendations)} recommendations to {unique_count} issues"
    )
    return {
        "auto_apply": recommendations,
    }


def build_ticket_details(recommendations: list[dict], token_storage, user_id: str) -> list[dict]:
    """Build detailed ticket information grouped by ticket ID.

    Args:
        recommendations: List of recommendation dictionaries
        token_storage: TokenStorage instance for Jira access
        user_id: User identifier

    Returns:
        List of ticket detail dictionaries with format:
        [
            {
                "ticket": "RHIDP-123",
                "title": "Login fails with SSO",
                "team": "RHDH Security",
                "components": ["Keycloak Provider", "RBAC"]
            }
        ]
    """
    from jira import JIRA

    # Get Jira credentials from environment or database
    if token_storage is None:
        # Use environment variables
        jira_token_str = os.getenv("JIRA_API_TOKEN")
        jira_server = os.getenv("JIRA_SERVER_URL", "https://issues.redhat.com")
        if not jira_token_str:
            logger.error("No JIRA_API_TOKEN found in environment")
            return []
        jira_token = {"token": jira_token_str, "server_url": jira_server}
    else:
        # Use database
        jira_token = token_storage.get_token("jira", user_id)
        if not jira_token:
            logger.error("No Jira token found for fetching ticket titles")
            return []

    try:
        jira = JIRA(server=jira_token["server_url"], token_auth=jira_token["token"])
    except Exception as e:
        logger.error(f"Failed to connect to Jira for fetching titles: {e}")
        return []

    # Group recommendations by ticket
    by_ticket = {}
    for rec in recommendations:
        ticket = rec["ticket"]
        if ticket not in by_ticket:
            by_ticket[ticket] = {"team": None, "components": [], "title": None}

        # Extract team and components from recommendations
        if rec["field"] == "team":
            by_ticket[ticket]["team"] = rec["recommended"]
        elif rec["field"] == "components":
            # Split comma-separated components
            components = [c.strip() for c in rec["recommended"].split(",")]
            by_ticket[ticket]["components"].extend(components)

    # Fetch ticket titles from Jira
    for ticket in by_ticket.keys():
        try:
            issue = jira.issue(ticket, fields="summary")
            by_ticket[ticket]["title"] = issue.fields.summary
            logger.debug(f"Fetched title for {ticket}")
        except Exception as e:
            logger.warning(f"Failed to fetch title for {ticket}: {e}")
            by_ticket[ticket]["title"] = ticket  # Fallback to ticket ID

    # Build final list
    ticket_details = []
    for ticket, details in sorted(by_ticket.items()):
        item = {
            "ticket": ticket,
            "title": details["title"] or ticket,  # Fallback to ticket ID if title not fetched
        }
        if details["team"]:
            item["team"] = details["team"]
        if details["components"]:
            item["components"] = details["components"]
        ticket_details.append(item)

    return ticket_details


def load_team_id_map() -> dict[str, str]:
    """Load team name to ID mapping from config file.

    Returns:
        Dictionary mapping team names to team IDs
    """
    try:
        with open(CONFIG_FILE_PATH) as f:
            teams_data = json.load(f)

        team_id_map = {}
        for team_name, team_data in teams_data.items():
            if "id" in team_data:
                team_id_map[team_name] = team_data["id"]
        return team_id_map
    except Exception as e:
        logger.error(f"Failed to load team ID map: {e}")
        return {}


def apply_recommendations(recommendations: list[dict], token_storage, user_id: str) -> dict:
    """Apply triage recommendations to Jira.

    Args:
        recommendations: List of recommendations to apply
        token_storage: TokenStorage instance
        user_id: User identifier

    Returns:
        Dictionary with 'applied' and 'failed' lists
    """
    from jira import JIRA

    team_id_map = load_team_id_map()

    # Get Jira credentials from environment or database
    if token_storage is None:
        # Use environment variables
        jira_token_str = os.getenv("JIRA_API_TOKEN")
        jira_server = os.getenv("JIRA_SERVER_URL", "https://issues.redhat.com")
        if not jira_token_str:
            logger.error("No JIRA_API_TOKEN found in environment")
            return {"applied": [], "failed": recommendations}
        jira_token = {"token": jira_token_str, "server_url": jira_server}
    else:
        # Use database
        jira_token = token_storage.get_token("jira", user_id)
        if not jira_token:
            logger.error("No Jira token found")
            return {"applied": [], "failed": recommendations}

    try:
        jira = JIRA(server=jira_token["server_url"], token_auth=jira_token["token"])
    except Exception as e:
        logger.error(f"Failed to connect to Jira: {e}")
        return {"applied": [], "failed": recommendations}

    applied = []
    failed = []

    # Group by ticket to batch updates
    by_ticket = {}
    for rec in recommendations:
        ticket = rec["ticket"]
        if ticket not in by_ticket:
            by_ticket[ticket] = []
        by_ticket[ticket].append(rec)

    # Apply updates ticket by ticket
    for ticket, updates in by_ticket.items():
        try:
            logger.info(f"Updating {ticket} ({len(updates)} fields)")

            # Prepare update fields
            update_fields = {}

            for update in updates:
                field = update["field"]
                recommended = update["recommended"]

                if field == "team":
                    team_id = team_id_map.get(recommended)
                    if team_id:
                        update_fields["customfield_12313240"] = team_id
                    else:
                        logger.error(f"Unknown team name '{recommended}' - not found in team_id_map")
                        continue
                elif field == "components":
                    # Components is a list of component names
                    component_names = [c.strip() for c in recommended.split(",")]
                    update_fields["components"] = [{"name": name} for name in component_names]

            # Update issue
            if update_fields:
                issue = jira.issue(ticket)
                issue.update(fields=update_fields)
                logger.info(f"✓ Updated {ticket}: {list(update_fields.keys())}")

                # Mark all updates for this ticket as applied
                applied.extend(updates)
            else:
                logger.warning(f"No valid fields to update for {ticket}")
                failed.extend(updates)

        except Exception as e:
            logger.error(f"Failed to update {ticket}: {type(e).__name__}")
            failed.extend(updates)

    unique_applied = len(set(item["ticket"] for item in applied))
    unique_failed = len(set(item["ticket"] for item in failed))
    logger.info(
        f"Applied {len(applied)} recommendations to {unique_applied} issues, "
        f"failed {len(failed)} recommendations on {unique_failed} issues"
    )
    return {"applied": applied, "failed": failed}


def run_triage(
    user_id: str,
    db_path: str,
    jql_filter: str | None = None,
    dry_run: bool = False,
    confidence_threshold: int = 80,
    json_output: bool = False,
) -> dict:
    """Run automated triage.

    Args:
        user_id: User identifier
        db_path: Database file path
        jql_filter: Custom JQL filter (optional)
        dry_run: If True, don't apply changes
        confidence_threshold: Minimum confidence for auto-apply (0-100)
        json_output: If True, output JSON instead of human-readable

    Returns:
        Results dictionary with metrics and details
    """
    # Verify JIRA_API_TOKEN is set
    if not os.getenv("JIRA_API_TOKEN"):
        logger.error("JIRA_API_TOKEN environment variable is required")
        sys.exit(1)

    logger.info("Using JIRA_API_TOKEN from environment")

    # Create minimal database for agent (session storage only, no credentials)
    db_path_obj = Path(db_path)
    db_path_obj.parent.mkdir(parents=True, exist_ok=True)
    shared_db = SqliteDb(db_file=db_path)

    # TokenStorage not needed - JiraConfig will use env var
    token_storage = None

    # Create Jira Triager agent
    logger.info(f"Creating Jira Triager for user {user_id}")
    from agentllm.agents.jira_triager import JiraTriager

    agent = JiraTriager(
        shared_db=shared_db,
        token_storage=token_storage,
        user_id=user_id,
        temperature=0.2,  # Low temperature for consistency
    )

    # Build triage prompt (use default JQL if none provided)
    effective_jql = jql_filter or DEFAULT_JQL_FILTER
    prompt = f"Triage all issues matching this JQL filter: {effective_jql}"

    # Only log JQL if using default filter (custom filters may contain customer data)
    if jql_filter is None:
        logger.info(f"Running triage with default JQL filter")
    else:
        logger.info("Running triage with custom JQL filter (not logged for privacy)")

    # Run agent and collect response
    response_text = ""
    try:
        result = agent.run(prompt)
        # Handle RunOutput object (non-streaming response)
        if hasattr(result, "content"):
            response_text = result.content
        elif hasattr(result, "text"):
            response_text = result.text
        else:
            # Fallback: convert to string
            response_text = str(result)

        if not json_output:
            print(response_text, flush=True)
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "total": 0,
            "auto_apply": 0,
            "applied": 0,
            "failed": 0,
        }

    if not json_output:
        print("\n")

    # Parse recommendations from response
    logger.info("Parsing triage recommendations")
    recommendations = parse_triage_table(response_text)

    if not recommendations:
        logger.warning("No recommendations found")
        return {
            "success": True,
            "total": 0,
            "auto_apply": 0,
            "applied": 0,
            "failed": 0,
            "recommendations": [],
        }

    # Classify by confidence (applies all recommendations)
    classified = classify_recommendations(recommendations, confidence_threshold)

    # Count unique issues (not fields)
    unique_total = len(set(item["ticket"] for item in recommendations))
    unique_auto_apply = len(set(item["ticket"] for item in classified["auto_apply"]))

    # Build detailed ticket information with team and component assignments
    auto_apply_items = build_ticket_details(classified["auto_apply"], token_storage, user_id)

    results = {
        "success": True,
        "total": unique_total,
        "auto_apply": unique_auto_apply,
        "applied": 0,
        "failed": 0,
        "auto_apply_items": auto_apply_items,
        "applied_items": [],
        "failed_items": [],
    }

    # Apply all recommendations (if not dry-run)
    if not dry_run and classified["auto_apply"]:
        unique_apply_count = len(set(item["ticket"] for item in classified["auto_apply"]))
        logger.info(
            f"Applying {len(classified['auto_apply'])} recommendations "
            f"to {unique_apply_count} issues"
        )
        apply_results = apply_recommendations(classified["auto_apply"], token_storage, user_id)

        # Count unique issues (not fields)
        unique_applied = len(set(item["ticket"] for item in apply_results["applied"]))
        unique_failed = len(set(item["ticket"] for item in apply_results["failed"]))

        # Build detailed ticket information with team and component assignments
        applied_items = build_ticket_details(apply_results["applied"], token_storage, user_id)
        failed_items = build_ticket_details(apply_results["failed"], token_storage, user_id)

        results["applied"] = unique_applied
        results["failed"] = unique_failed
        results["applied_items"] = applied_items
        results["failed_items"] = failed_items
    elif dry_run:
        unique_auto_apply_count = len(set(item["ticket"] for item in classified["auto_apply"]))
        logger.info(
            f"Dry-run mode: Would apply {len(classified['auto_apply'])} recommendations "
            f"to {unique_auto_apply_count} issues"
        )

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Automated Jira triage with confidence-based auto-apply")

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying (default: False)",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply all recommendations (default: False)",
    )

    parser.add_argument(
        "--jql",
        type=str,
        help="Custom JQL filter (optional)",
    )

    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Output JSON instead of human-readable (default: False)",
    )

    parser.add_argument(
        "--user-id",
        type=str,
        default=AUTOMATION_USER_ID,
        help=f"User ID for automation (default: {AUTOMATION_USER_ID})",
    )

    parser.add_argument(
        "--db-path",
        type=str,
        default=DB_PATH,
        help=f"Database file path (default: {DB_PATH})",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.dry_run and not args.apply:
        logger.error("Must specify either --dry-run or --apply")
        sys.exit(1)

    # Run triage
    results = run_triage(
        user_id=args.user_id,
        db_path=args.db_path,
        jql_filter=args.jql,
        dry_run=args.dry_run,
        confidence_threshold=80,  # Not used, but kept for backward compatibility
        json_output=args.json_output,
    )

    # Output results
    if args.json_output:
        print(json.dumps(results, indent=2))
    else:
        print("\n=== Triage Summary ===")
        print(f"Total recommendations: {results['total']}")
        print(f"To apply: {results['auto_apply']}")

        if not args.dry_run:
            print(f"Applied successfully: {results['applied']}")
            print(f"Failed to apply: {results['failed']}")

    # Exit codes
    if not results["success"]:
        sys.exit(1)  # Execution error
    elif results["failed"] > 0:
        sys.exit(1)  # Some updates failed
    else:
        sys.exit(0)  # Success


if __name__ == "__main__":
    main()
