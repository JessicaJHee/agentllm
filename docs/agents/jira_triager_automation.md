# Jira Triager: Automation Guide

## Overview

Automated Jira ticket triage runs on GitHub Actions schedule (every 4 hours, weekdays):

- **Auto-triages** untriaged tickets using AI recommendations
- **Auto-applies** high-confidence updates (≥80% threshold)
- **Slack notifications** with results and manual review items
- **JSON artifacts** for audit trails

**How It Works:**

```
GitHub Actions (Every 4 hours, Mon-Fri)
         ↓
Load config from: github.com/JessicaJHee/rhdh-jira-triager-knowledge
         ↓
Query Jira for untriaged tickets (empty team/component)
         ↓
AI analyzes each ticket → Generate recommendations
         ↓
Auto-apply recommendations ≥80% confidence
         ↓
Send Slack notification + Upload JSON artifact
```

## Prerequisites

### 1. Team Configuration

The automation reads team mappings from a **private GitHub repository**:

```
https://github.com/JessicaJHee/rhdh-jira-triager-knowledge/blob/main/rhdh-teams.json
```

This file contains team IDs, components, and members. The workflow automatically checks out this repo during execution (no manual setup needed).

### 2. GitHub Secrets

Add these secrets to your repository (**Settings → Secrets and variables → Actions**):

| Secret | Description | Required |
|--------|-------------|----------|
| `JIRA_API_TOKEN` | Jira API token from issues.redhat.com | ✅ Yes |
| `GEMINI_API_KEY` | Gemini API key for AI analysis | ✅ Yes |
| `SLACK_WEBHOOK_URL` | Slack webhook for notifications | ⚠️ Optional |

**To get a Jira API token:**
1. Go to https://issues.redhat.com
2. Profile icon → Account Settings → Security → API Tokens
3. Create and copy token

**Hardcoded settings** (no configuration needed):
- Jira Server: `https://issues.redhat.com`
- Automation User: `jira-triager-bot`
- Config Location: `github.com/JessicaJHee/rhdh-jira-triager-knowledge`
- Default Filter: Untriaged tickets in RHIDP/RHDH projects

## Configuration

### Confidence Threshold

The automation auto-applies recommendations with **≥80% confidence** (default).

| Threshold | Behavior |
|-----------|----------|
| **80%+** | Auto-applied immediately |
| **<80%** | Flagged for manual review in Slack |

**Adjust threshold** via workflow input (see Manual Trigger below).

### Default Filter

The automation processes tickets matching:
- Projects: RHIDP, RHDH Support, RHDH Bugs
- Status: Not closed
- Missing: Team OR Component
- Excludes: Sub-tasks, Features, Outcomes

**Custom JQL filters** can be provided via manual trigger.

## Usage

### Scheduled Runs (Automatic)

The workflow runs **automatically every 4 hours on weekdays** (Mon-Fri).

No action required - just monitor Slack notifications.

### Manual Trigger

To run the automation manually:

1. Go to **Actions → Jira Auto-Triage → Run workflow**
2. Optional settings:
   - **Dry-run mode**: Preview recommendations without applying
   - **Confidence threshold**: Change from default 80%
   - **Custom JQL filter**: Override default filter
3. Click **Run workflow**

### Adjusting Schedule

Edit `.github/workflows/jira-auto-triage.yml` to change the schedule:

```yaml
# Default: Every 4 hours on weekdays
schedule:
  - cron: "0 */4 * * 1-5"

# Examples:
# Every 2 hours: "0 */2 * * 1-5"
# Daily at 9am UTC: "0 9 * * *"
# Twice daily: "0 9,14 * * 1-5"
```

## Monitoring

### Slack Notifications

Each run sends a Slack notification with:

- **Metrics**: Total recommendations, auto-applied, failed, manual review
- **Failed updates**: First 5 items that failed to apply
- **Manual review**: First 5 items below confidence threshold
- **Workflow link**: Direct link to GitHub Actions run

**Example:**
```
⚠️ Jira Auto-Triage Results

Total: 10 | Auto-Applied: 7 | Failed: 1 | Manual Review: 2

Failed Updates:
• RHIDP-123 - team: RHIDP - Security

Manual Review (< 80%):
• RHIDP-124 - team: RHIDP - Frontend (75%)
• RHIDP-125 - components: Catalog (70%)
```

### Artifacts

JSON results are uploaded to GitHub Actions for audit trail:
- **Location**: Actions → Workflow run → Artifacts
- **Name**: `triage-results-{run_number}`
- **Retention**: 30 days

## Troubleshooting

### Missing Secrets Error

Add `JIRA_API_TOKEN` and `GEMINI_API_KEY` to repository secrets (Settings → Secrets and variables → Actions).

### Manual Review Items

Items below 80% confidence are flagged for manual review in Slack. This is expected behavior, not an error.

**Common causes:**
- New components not in team mappings
- Ambiguous ticket descriptions
- Keywords match multiple teams

**Action**: Review the config file and add missing component mappings if needed.

### Failed Updates

Check the JSON artifact for error details. Common causes:
- Invalid team IDs in config
- Jira API permissions
- Network issues

### Config File Not Found

Ensure the private repo `JessicaJHee/rhdh-jira-triager-knowledge` is accessible and contains `rhdh-teams.json`.

## Best Practices

### Initial Setup

1. **Start with dry-run**: Test for 1-2 weeks before enabling auto-apply
2. **Monitor Slack**: Review notifications to understand patterns
3. **Update config**: Add missing component mappings as needed

### Ongoing Maintenance

1. **Update team config**: When team structure changes, update `rhdh-teams.json` in the config repo
2. **Review manual items**: Check low-confidence items in Slack for patterns
3. **Rotate tokens**: Refresh Jira API token every 6-12 months
4. **Monitor failures**: Investigate failed updates via JSON artifacts

### Adjusting Confidence

Start conservative (80%), increase gradually based on accuracy:
- **85%+**: Safest, more manual review
- **80%**: Recommended balance (default)
- **75%**: More automation, some false positives

## Updating Team Configuration

To update team mappings when your team structure changes:

1. Go to https://github.com/JessicaJHee/rhdh-jira-triager-knowledge
2. Edit `rhdh-teams.json`
3. Commit changes to main branch
4. Next automation run will use updated config automatically

No code changes or redeployment needed!
