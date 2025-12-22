# Jira Triager - User Guide (Interactive Mode)

> **Note:** This guide covers interactive chat usage. For automated CI/CD setup, see:
> - [Automation Guide](jira_triager_automation.md) - GitHub Actions setup and configuration

## Overview

Analyzes Jira tickets and recommends team/component assignments using component mappings, keyword analysis, and assignee validation.

## Quick Start

**Prerequisites**: Jira API token + Google Drive OAuth + `JIRA_TRIAGER_GDRIVE_FOLDER_ID` env var

**First Use**:
1. Provide Jira token: `my jira token is TOKEN_HERE and server is https://issues.redhat.com`
2. Authorize Google Drive (OAuth URL provided by agent)
3. Start triaging: `Triage RHIDP-8796`

## Usage

**Single ticket**: `Triage RHIDP-8796`
- Agent analyzes and shows recommendations
- Shows summary table with ticket
- Asks for confirmation before updating

**Batch triage**: `Triage all issues in queue`
- Agent finds all tickets from configured filter
- Processes ALL tickets first
- Shows ONE consolidated table with ALL tickets
- Asks for confirmation before updating all

## Update Workflow

**Single Ticket:**
1. Agent analyzes ticket
2. Shows recommendations
3. Asks: "Would you like me to apply these changes to Jira?"
4. Shows summary table
5. Waits for "yes" confirmation
6. Updates empty fields only

**Batch Triage:**
1. Agent searches for all tickets (using filter)
2. Processes ALL tickets (triages each one)
3. Shows ONE table with ALL recommendations:
   ```
   | Ticket | Summary | Field | Current | Recommended | Confidence | Action |
   |--------|---------|-------|---------|-------------|------------|--------|
   | RHIDP-100 | Login fails | Team<br>Components | (empty)<br>Catalog | Security<br>Catalog, Keycloak | 95%<br>90% | NEW<br>APPEND |
   | RHIDP-101 | Operator crash | Team<br>Components | Install<br>(empty) | Already Set<br>Operator | -<br>85% | SKIP<br>NEW |
   ```

   Note: Each ticket shown as single row with Team/Components using `<br>` tags

4. Asks: "Ready to apply these changes? (yes/no)"
5. Updates all approved tickets
6. Reports progress and final summary

**Action Codes:**
- NEW: Field is empty, will add new value
- APPEND: Will add additional components to existing ones (never replaces team)
- SKIP: Field already correct, no change

## Confidence Scores

- 95%: Specific component + keywords + assignee
- 90%: Component + keywords align
- 85%: Clear component mapping
- 75%: Strong keywords only
- 60%: General component only
- <50%: Ask for guidance

**Component Validation**: The agent automatically validates that recommended components
exist in the Jira project before suggesting them. Invalid components are rejected.

## Configuration

**Google Drive Folder** (`JIRA_TRIAGER_GDRIVE_FOLDER_ID`) OR **Local File** (`JIRA_TRIAGER_CONFIG_FILE`):
- `rhdh-teams.json` - Team config (IDs, components, members)

**rhdh-teams.json example**:
```json
{
  "RHIDP - Security": {
    "id": "4267",
    "components": ["Keycloak provider", "RBAC Plugin"],
    "members": ["Jessica He", "John Doe"]
  }
}
```

## Troubleshooting

- **No recommendation**: Add components or provide more context
- **Configuration not loaded**: Check `JIRA_TRIAGER_GDRIVE_FOLDER_ID` and folder permissions
- **Update failed**: Verify team ID in TEAM_ID_MAP
