#!/usr/bin/env python3
"""Automated Jira triage with confidence-based auto-apply.

This script runs Jira Triager in headless mode for CI/CD automation.
It processes triage recommendations and auto-applies changes based on confidence thresholds.

Usage:
    # Dry-run (preview only)
    python scripts/auto_triage.py --dry-run

    # Apply with 80% confidence threshold
    python scripts/auto_triage.py --apply --confidence 80

    # Custom JQL filter
    python scripts/auto_triage.py --apply --jql "project=RHIDP AND status='To Do'"

    # JSON output for CI/CD
    python scripts/auto_triage.py --apply --json-output

Exit Codes:
    0 - Success (all applied successfully)
    1 - Failures (some updates failed)
    2 - Manual review required (some items below confidence threshold)
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

from agentllm.db.token_storage import TokenStorage
from agno.db.sqlite import SqliteDb

# Import toolkit configs to register token types with global registry
from agentllm.agents.toolkit_configs.jira_config import JiraConfig  # noqa: F401

# Constants
AUTOMATION_USER_ID = "jira-triager-bot"
DB_PATH = "tmp/agent-data/agno_sessions.db"


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

        ticket, summary, field, current, recommended, confidence_str, action = cols

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

        recommendations.append({
            "ticket": ticket,
            "summary": summary,
            "field": field.lower(),
            "current": current,
            "recommended": recommended,
            "confidence": confidence,
            "action": action,
        })

    logger.info(f"Parsed {len(recommendations)} recommendations from table")
    return recommendations


def classify_recommendations(recommendations: list[dict], threshold: int) -> dict:
    """Classify recommendations by confidence threshold.

    Args:
        recommendations: List of recommendation dictionaries
        threshold: Minimum confidence for auto-apply (0-100)

    Returns:
        Dictionary with 'auto_apply' and 'manual_review' lists
    """
    auto_apply = []
    manual_review = []

    for rec in recommendations:
        if rec["confidence"] >= threshold:
            auto_apply.append(rec)
        else:
            manual_review.append(rec)

    logger.info(f"Classification: {len(auto_apply)} auto-apply, {len(manual_review)} manual review")
    return {
        "auto_apply": auto_apply,
        "manual_review": manual_review,
    }


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

    # Get Jira credentials
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
                    # Team field is customfield_12313240, value is team ID
                    update_fields["customfield_12313240"] = {"name": recommended}
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
            logger.error(f"Failed to update {ticket}: {e}")
            failed.extend(updates)

    logger.info(f"Applied {len(applied)}, failed {len(failed)}")
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
    # Load encryption key from setup script
    db_path_obj = Path(db_path)
    key_file = db_path_obj.parent / ".encryption_key"
    if not key_file.exists():
        logger.error(f"Encryption key file not found: {key_file}")
        logger.error("Run scripts/setup_database_from_secrets.py first")
        sys.exit(1)

    encryption_key = key_file.read_text().strip()
    logger.debug("Loaded encryption key from setup")

    # Load database
    logger.info(f"Loading database: {db_path}")
    shared_db = SqliteDb(db_file=db_path)
    token_storage = TokenStorage(agno_db=shared_db, encryption_key=encryption_key)

    # Verify user is configured
    if not token_storage.get_token("jira", user_id):
        logger.error(f"User {user_id} not configured (no Jira token)")
        sys.exit(1)

    # Create Jira Triager agent
    logger.info(f"Creating Jira Triager for user {user_id}")
    from agentllm.agents.jira_triager import JiraTriager

    agent = JiraTriager(
        shared_db=shared_db,
        token_storage=token_storage,
        user_id=user_id,
        temperature=0.2,  # Low temperature for consistency
    )

    # Build triage prompt
    if jql_filter:
        prompt = f"Triage all issues matching this JQL filter: {jql_filter}"
    else:
        prompt = "Triage all issues in the default queue"

    logger.info(f"Running triage: {prompt}")

    # Run agent and collect response
    response_text = ""
    try:
        for chunk in agent.run(prompt):
            if hasattr(chunk, "text") and chunk.text:
                response_text += chunk.text
                if not json_output:
                    print(chunk.text, end="", flush=True)
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "total": 0,
            "auto_apply": 0,
            "manual_review": 0,
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
            "manual_review": 0,
            "applied": 0,
            "failed": 0,
            "recommendations": [],
        }

    # Classify by confidence
    classified = classify_recommendations(recommendations, confidence_threshold)

    results = {
        "success": True,
        "total": len(recommendations),
        "auto_apply": len(classified["auto_apply"]),
        "manual_review": len(classified["manual_review"]),
        "applied": 0,
        "failed": 0,
        "applied_items": [],
        "failed_items": [],
        "manual_review_items": classified["manual_review"],
    }

    # Apply high-confidence recommendations (if not dry-run)
    if not dry_run and classified["auto_apply"]:
        logger.info(f"Applying {len(classified['auto_apply'])} high-confidence recommendations")
        apply_results = apply_recommendations(classified["auto_apply"], token_storage, user_id)

        results["applied"] = len(apply_results["applied"])
        results["failed"] = len(apply_results["failed"])
        results["applied_items"] = apply_results["applied"]
        results["failed_items"] = apply_results["failed"]
    elif dry_run:
        logger.info(f"Dry-run mode: Would apply {len(classified['auto_apply'])} recommendations")

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
        help="Apply high-confidence recommendations (default: False)",
    )

    parser.add_argument(
        "--confidence",
        type=int,
        default=80,
        help="Minimum confidence threshold for auto-apply (default: 80)",
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
        confidence_threshold=args.confidence,
        json_output=args.json_output,
    )

    # Output results
    if args.json_output:
        print(json.dumps(results, indent=2))
    else:
        print("\n=== Triage Summary ===")
        print(f"Total recommendations: {results['total']}")
        print(f"Auto-apply (≥{args.confidence}%): {results['auto_apply']}")
        print(f"Manual review (<{args.confidence}%): {results['manual_review']}")

        if not args.dry_run:
            print(f"Applied successfully: {results['applied']}")
            print(f"Failed to apply: {results['failed']}")

    # Exit codes
    if not results["success"]:
        sys.exit(1)  # Execution error
    elif results["failed"] > 0:
        sys.exit(1)  # Some updates failed
    elif results["manual_review"] > 0:
        sys.exit(2)  # Manual review required
    else:
        sys.exit(0)  # Success


if __name__ == "__main__":
    main()
