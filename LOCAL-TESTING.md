# Local Testing Guide - Jira Auto-Triage

Quick guide to test the Jira triage workflow locally before deploying to production.

## Prerequisites

- [ ] Podman or Docker installed
- [ ] Jira API token (from https://issues.redhat.com)
- [ ] Gemini API key
- [ ] `rhdh-teams.json` config file (from JessicaJHee/rhdh-jira-triager-knowledge repo)

## Step 1: Get Your Jira API Token

```bash
# 1. Go to https://issues.redhat.com
# 2. Click profile icon → Account Settings → Security → API Tokens
# 3. Create new token and copy it
export JIRA_API_TOKEN="your-token-here"

# Verify it works
curl -H "Authorization: Bearer $JIRA_API_TOKEN" \
  https://issues.redhat.com/rest/api/2/myself
```

## Step 2: Get Config File

```bash
# Clone the private config repo (if you have access)
git clone https://github.com/JessicaJHee/rhdh-jira-triager-knowledge.git /tmp/jira-config
export CONFIG_FILE="/tmp/jira-config/rhdh-teams.json"

# OR if you already have it locally
export CONFIG_FILE="/path/to/your/rhdh-teams.json"

# Verify config file exists
ls -la "$CONFIG_FILE"
```

## Step 3: Set Environment Variables

```bash
# Required
export JIRA_API_TOKEN="your-jira-api-token"
export GEMINI_API_KEY="your-gemini-api-key"

# Optional
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."  # For Slack notifications
export JQL_FILTER="project=RHIDP AND status='To Do' LIMIT 5"      # Custom filter (limits to 5 for testing)

# Test mode
export DRY_RUN="true"
export LOGURU_LEVEL="INFO"
export AGNO_DEBUG="false"
```

## Step 4: Build Container Locally

```bash
# From the agentllm repo root
cd /Users/jhe/git/ai-projects/agentllm

# Build AgentLLM container (includes triage scripts)
make build-agentllm

# Verify build
podman images | grep agentllm
```

Expected output:
```
codeberg.org/b4mad/agentllm/agentllm  v0.x.x-abc1234  ...  1.5GB  ...
```

## Step 5: Run Dry-Run Test

```bash
# Run triage in dry-run mode (no changes to Jira)
# Uses environment variables set in Step 3
podman run --rm \
  -v "$CONFIG_FILE:/config/rhdh-teams.json:ro" \
  -e JIRA_API_TOKEN \
  -e GEMINI_API_KEY \
  -e DRY_RUN \
  -e LOGURU_LEVEL \
  -e AGNO_DEBUG \
  codeberg.org/b4mad/agentllm/agentllm:latest \
  bash /app/scripts/run_triage.sh
```

## Expected Output

```
=== Jira Auto-Triage Workflow ===
Mode: DRY-RUN
Config: /config/rhdh-teams.json

Running auto-triage...
Using JIRA_API_TOKEN from environment
Creating Jira Triager for user jira-triager-bot
Running triage with default JQL filter

[Agent processes issues...]

| Ticket      | Summary                     | Field      | Current | Recommended | Confidence | Action |
|-------------|----------------------------|------------|---------|-------------|------------|--------|
| RHIDP-1234  | Login fails with SSO       | team       | -       | Security    | 95%        | NEW    |
| RHIDP-1234  | Login fails with SSO       | components | -       | RBAC        | 90%        | NEW    |
| RHIDP-5678  | Plugin API error           | team       | -       | Plugins     | 92%        | NEW    |

Step 3: Skipping Slack notification (SLACK_WEBHOOK_URL not set)

=== Triage Summary ===
Total issues: 3
Would apply: 3

✅ Triage completed successfully
```

## Step 6 (Optional): Test with Custom JQL

```bash
# Test with a specific issue or smaller query
export JQL_FILTER="key=RHIDP-1234"

podman run --rm \
  -v "$CONFIG_FILE:/config/rhdh-teams.json:ro" \
  -e JIRA_API_TOKEN \
  -e GEMINI_API_KEY \
  -e DRY_RUN \
  -e JQL_FILTER \
  codeberg.org/b4mad/agentllm/agentllm:latest \
  bash /app/scripts/run_triage.sh
```

## Step 7 (Optional): Test Slack Notification

```bash
# Test with Slack webhook (still dry-run, won't update Jira)
# Make sure SLACK_WEBHOOK_URL is set in Step 3
podman run --rm \
  -v "$CONFIG_FILE:/config/rhdh-teams.json:ro" \
  -e JIRA_API_TOKEN \
  -e GEMINI_API_KEY \
  -e SLACK_WEBHOOK_URL \
  -e DRY_RUN \
  codeberg.org/b4mad/agentllm/agentllm:latest \
  bash /app/scripts/run_triage.sh
```

## Step 8 (CAREFUL): Test Apply Mode

⚠️ **WARNING**: This will actually update Jira issues!

Only do this if you have a test JIRA project or are ready to apply changes.

```bash
# Use a limited JQL filter for safety
export JQL_FILTER="project=TEST-PROJECT AND status='To Do' LIMIT 2"
export DRY_RUN="false"  # APPLY MODE!

podman run --rm \
  -v "$CONFIG_FILE:/config/rhdh-teams.json:ro" \
  -e JIRA_API_TOKEN \
  -e GEMINI_API_KEY \
  -e DRY_RUN \
  -e JQL_FILTER \
  codeberg.org/b4mad/agentllm/agentllm:latest \
  bash /app/scripts/run_triage.sh
```

## Troubleshooting

### Issue: "JIRA_API_TOKEN environment variable is required"

**Solution**: Make sure you exported the variable:
```bash
export JIRA_API_TOKEN="your-token-here"
echo $JIRA_API_TOKEN  # Should print your token
```

### Issue: "Config file not found"

**Solution**: Verify path and use absolute path:
```bash
ls -la "$CONFIG_FILE"

# Use absolute path
export CONFIG_FILE="/full/path/to/rhdh-teams.json"
```

### Issue: "Failed to connect to Jira"

**Solution**: Test your token manually:
```bash
curl -H "Authorization: Bearer $JIRA_API_TOKEN" \
  https://issues.redhat.com/rest/api/2/myself
```

### Issue: Container not found

**Solution**: Build the container first:
```bash
make build-agentllm
```

### Issue: Permission denied on config file

**Solution**: Check file permissions:
```bash
chmod 644 "$CONFIG_FILE"
```

## Quick Test Script

Save this as `test-triage.sh`:

```bash
#!/bin/bash
set -euo pipefail

# Configuration
export JIRA_API_TOKEN="${JIRA_API_TOKEN:-}"
export GEMINI_API_KEY="${GEMINI_API_KEY:-}"
export CONFIG_FILE="${CONFIG_FILE:-./tmp/rhdh-teams.json}"

# Validate
if [ -z "$JIRA_API_TOKEN" ]; then
  echo "Error: JIRA_API_TOKEN not set"
  exit 1
fi

if [ -z "$GEMINI_API_KEY" ]; then
  echo "Error: GEMINI_API_KEY not set"
  exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
  echo "Error: Config file not found: $CONFIG_FILE"
  exit 1
fi

# Build
echo "Building container..."
make build-agentllm

# Test dry-run
echo "Running dry-run test..."
DRY_RUN=true LOGURU_LEVEL=INFO podman run --rm \
  -v "$CONFIG_FILE:/config/rhdh-teams.json:ro" \
  -e JIRA_API_TOKEN \
  -e GEMINI_API_KEY \
  -e DRY_RUN \
  -e LOGURU_LEVEL \
  codeberg.org/b4mad/agentllm/agentllm:latest \
  bash /app/scripts/run_triage.sh

echo "✅ Test completed!"
```

Then run:
```bash
chmod +x test-triage.sh
./test-triage.sh
```

## Alternative: Test Using Main Container

If you already have the main AgentLLM container running via compose:

```bash
# Copy scripts into running container
podman cp scripts/ agentllm-proxy:/app/

# Install jq in running container
podman exec agentllm-proxy apt-get update
podman exec agentllm-proxy apt-get install -y jq

# Copy config file
podman cp /path/to/rhdh-teams.json agentllm-proxy:/config/rhdh-teams.json

# Run triage script
podman exec \
  -e JIRA_API_TOKEN="$JIRA_API_TOKEN" \
  -e GEMINI_API_KEY="$GEMINI_API_KEY" \
  -e DRY_RUN="true" \
  -e JIRA_TRIAGER_CONFIG_FILE="/config/rhdh-teams.json" \
  agentllm-proxy \
  bash /app/scripts/run_triage.sh
```

## Next Steps

After successful local testing:
- Share results with the team
- Prepare production cronjob setup
- See [CRONJOB-QUICKSTART.md](CRONJOB-QUICKSTART.md) for production deployment
