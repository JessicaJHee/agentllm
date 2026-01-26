#!/bin/bash
# SPDX-FileCopyrightText: © 2025 Christoph Görn <goern@b4mad.net>
# SPDX-License-Identifier: GPL-3.0-only

# Run Jira auto-triage workflow in container
# This script wraps the complete triage workflow for cronjob execution

set -euo pipefail

# Default values
DRY_RUN=${DRY_RUN:-false}
JQL_FILTER=${JQL_FILTER:-}
CONFIG_FILE=${JIRA_TRIAGER_CONFIG_FILE:-/config/rhdh-teams.json}

# Required environment variables
: "${JIRA_API_TOKEN:?JIRA_API_TOKEN environment variable is required}"
: "${GEMINI_API_KEY:?GEMINI_API_KEY environment variable is required}"

# Optional: Slack notification
SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL:-}

# Set logging
export LOGURU_LEVEL=${LOGURU_LEVEL:-INFO}
export AGNO_DEBUG=${AGNO_DEBUG:-false}

# Set config file path for the triager
export JIRA_TRIAGER_CONFIG_FILE="$CONFIG_FILE"

echo "=== Jira Auto-Triage Workflow ==="
echo "Mode: $([ "$DRY_RUN" = "true" ] && echo "DRY-RUN" || echo "APPLY")"
echo "Config: $CONFIG_FILE"
echo ""

# Run auto-triage
echo "Running auto-triage..."
CMD="python scripts/auto_triage.py --json-output"

if [ "$DRY_RUN" = "true" ]; then
    CMD="$CMD --dry-run"
else
    CMD="$CMD --apply"
fi

if [ -n "$JQL_FILTER" ]; then
    CMD="$CMD --jql '$JQL_FILTER'"
fi

# Run triage and capture output
eval "$CMD" > results.json
TRIAGE_EXIT_CODE=$?

if [ $TRIAGE_EXIT_CODE -ne 0 ]; then
    echo "ERROR: Triage failed (exit code $TRIAGE_EXIT_CODE)"
    cat results.json 2>/dev/null || echo "No results.json available"
    exit $TRIAGE_EXIT_CODE
fi
echo ""

# Step 3: Send Slack notification (if webhook URL provided)
if [ -n "$SLACK_WEBHOOK_URL" ]; then
    echo "Step 3: Sending Slack notification..."
    python scripts/send_slack_notification.py
    if [ $? -ne 0 ]; then
        echo "WARNING: Slack notification failed (non-fatal)"
    fi
else
    echo "Step 3: Skipping Slack notification (SLACK_WEBHOOK_URL not set)"
fi
echo ""

# Step 4: Check for failures
FAILED=$(jq -r '.failed // 0' results.json)
APPLIED=$(jq -r '.applied // 0' results.json)
TOTAL=$(jq -r '.total // 0' results.json)

echo "=== Triage Summary ==="
echo "Total issues: $TOTAL"
if [ "$DRY_RUN" = "true" ]; then
    echo "Would apply: $APPLIED"
else
    echo "Applied: $APPLIED"
    echo "Failed: $FAILED"
fi
echo ""

if [ "$FAILED" -gt 0 ]; then
    echo "⚠️ Warning: Triage completed with $FAILED failures"
    exit 1
fi

echo "✅ Triage completed successfully"
exit 0
