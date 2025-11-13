# Release Manager Prompt Maintenance Guide

This guide is for release managers, team leads, and anyone maintaining the Release Manager agent's extended system prompt.

## Overview

The Release Manager uses a **dual-prompt architecture**:

1. **Embedded System Prompt** (in code) - Agent's core identity and capabilities
2. **Extended System Prompt** (in Google Doc) - Operational instructions you maintain

**You maintain the Extended System Prompt.** This guide shows you how.

## What Goes in the Extended Prompt

### ✅ DO Include

**Jira Query Patterns:**
```
project = RHDH AND fixVersion = "{RELEASE_VERSION}" ORDER BY priority DESC
```
- Reusable templates with placeholders
- Team-specific JQL queries
- Custom field queries

**Response Instructions:**
- "When user asks X, query Y, format as Z"
- How to prioritize information
- What context to include
- Formatting guidelines

**Communication Guidelines:**
- Slack channels for different purposes
- When to escalate
- Meeting formats and agendas

**Process Workflows:**
- Your team's release process steps
- Timelines and milestones
- Risk identification patterns

**Team-Specific Information:**
- Google Drive folder locations
- Confluence page URLs
- Dashboard links
- Team contact information

### ❌ DO NOT Include

**Hardcoded Release Data:**
```
Bad:  "Release 1.5.0 is scheduled for 2025-01-15"
Good: "Query Jira for upcoming releases and their dates"
```

**User Documentation:**
```
Bad:  "Welcome to Release Manager! Here's how to use me..."
Good: "When user asks about status, query Jira and summarize..."
```

**Agent Capabilities:**
```
Bad:  "I can access Google Drive and Jira..."
Good: "Use Google Drive tools to fetch release calendar..."
```
These belong in the embedded prompt (code), not here.

## Getting Started

### Initial Setup

1. **Open the template:**
   - File: `docs/templates/release_manager_system_prompt.md`
   - This is your starting point

2. **Create Google Doc:**
   - Go to [Google Drive](https://drive.google.com)
   - Click "New" > "Google Docs"
   - Title it: "Release Manager System Prompt - [Your Team]"

3. **Copy content:**
   - Copy ALL content from the template file
   - Paste into your new Google Doc
   - Keep the markdown formatting

4. **Customize for your team:**
   - Update Jira project key (`RHDH` → your project)
   - Update Slack channel names
   - Update process timelines
   - Add team-specific queries

5. **Share the document:**
   - Click "Share" button
   - Set sharing to:
     - "Anyone with the link can view" (if public)
     - Or add specific users/groups (if private)
   - Copy the document URL

6. **Configure AgentLLM:**
   - Edit `.env.secrets` file
   - Set: `RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL=<your-doc-url>`
   - Restart services: `nox -s dev_build`

### Verifying Setup

1. **Start agent:**
   ```bash
   nox -s dev_build
   ```

2. **Check logs for:**
   ```
   ✅ Successfully fetched extended system prompt
   ```

3. **Test with agent:**
   ```
   User: "What's your process for releases?"
   Agent: [Should describe YOUR team's process]
   ```

## Making Updates

### When to Update

Update the prompt when:
- **Process changes** - New release workflow, different timelines
- **Jira structure changes** - New custom fields, different project keys
- **Communication changes** - New Slack channels, different escalation paths
- **Query patterns change** - Better JQL queries discovered
- **Feedback from users** - Agent not responding as expected

### How to Update

1. **Edit the Google Doc directly:**
   - No code changes needed
   - No deployment required
   - Just save the doc

2. **Changes take effect when:**
   - User re-authorizes Google Drive (invalidates cache)
   - Agent is recreated (cache cleared)
   - Application restarts

3. **Force immediate update:**
   ```bash
   # Restart the services
   nox -s dev_stop
   nox -s dev_build
   ```

### Testing Updates

**Development Workflow:**

1. **Create dev copy:**
   - Duplicate your prod Google Doc
   - Name it: "Release Manager System Prompt - DEV"

2. **Configure dev environment:**
   ```bash
   # In .env
   RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL=<dev-doc-url>
   ```

3. **Make and test changes:**
   - Edit dev doc
   - Restart: `nox -s dev_build`
   - Test with agent
   - Verify responses match expectations

4. **Deploy to production:**
   - Copy working content from dev doc to prod doc
   - Update production `.env.secrets` to use prod doc URL
   - Restart production services

**Single-User Testing:**

If you don't have separate dev/prod:

1. Edit the doc
2. Restart local dev environment
3. Test thoroughly
4. Leave changes (production will pick up on next restart)

## Customization Examples

### Example 1: Add New Jira Query

**Scenario:** You want to track documentation tickets separately.

**Add to "Jira Query Patterns" section:**

```markdown
### Documentation Tickets

**Query Purpose:** Find all documentation tickets for a release

**JQL:**
\```
project = RHDH AND fixVersion = "{RELEASE_VERSION}" AND labels = "documentation" ORDER BY status
\```

**Example:**
\```
project = RHDH AND fixVersion = "1.5.0" AND labels = "documentation" ORDER BY status
\```
```

### Example 2: Update Slack Channels

**Scenario:** Your team reorganized Slack channels.

**Update "Communication Guidelines" section:**

```markdown
### Slack Channels

**Release Announcements:**
- Channel: `#releases-public`  ← Changed from #rhdh-releases
- When: Major milestones, release candidates, final releases

**Internal Discussions:**
- Channel: `#dev-releases-internal`  ← Changed from #rhdh-dev
- When: Daily updates, blocker discussions
```

### Example 3: Add Custom Response Instruction

**Scenario:** Users often ask about specific feature status.

**Add to "Response Instructions" section:**

```markdown
### "Is feature X included in release Y.Z.W?"

**Actions:**
1. Query Jira:
   \```
   project = RHDH AND fixVersion = "Y.Z.W" AND summary ~ "feature-name"
   \```
2. Check ticket status
3. If Done: Confirm inclusion with ticket link
4. If In Progress: Provide status and ETA
5. If Not Found: Search without fixVersion filter

**Response Format:**
\```markdown
**Feature Status for Release Y.Z.W:**

- [JIRA-123] Feature Name
- Status: Done / In Progress / Planned
- Details: [Brief description]
- [Link to ticket]
\```
```

### Example 4: Adjust Release Timeline

**Scenario:** Your team moved to shorter release cycles.

**Update "Process Workflows" → "Y-Stream Release Process":**

```markdown
1. **Planning Phase** (1 week before code freeze)  ← Changed from 2-3 weeks
   - Define scope and features
   ...

2. **Development Phase** (2-3 weeks)  ← Changed from 4-6 weeks
   - Regular progress checks
   ...
```

## Best Practices

### Writing Effective Instructions

**Be Specific:**
```
Bad:  "Help users with releases"
Good: "When user asks for release status, query Jira for fixVersion tickets,
       group by status, identify blockers, and provide completion percentage"
```

**Use Examples:**
```
When describing a format, always provide an example:

**Response Format:**
\```markdown
## Release 1.5.0 Status
**Progress:** 75% complete
...
\```
```

**Think Like an Agent:**
```
Bad:  "Users should check Jira for status"
Good: "Query Jira for status and present to user"
```

You're instructing the agent, not the user.

### Maintenance Schedule

**Monthly Review:**
- Verify Jira queries still work
- Check if Slack channels are current
- Review recent agent interactions for issues
- Update any outdated information

**After Process Changes:**
- Update workflow sections immediately
- Test with real scenarios
- Update examples to match new process

**After Major Releases:**
- Conduct retrospective on agent performance
- Gather feedback from team
- Identify improvements needed
- Update prompt accordingly

### Version Control

**Track Changes:**

Add to bottom of Google Doc:

```markdown
---
## Change Log

**2025-01-15:**
- Updated Y-stream timeline to 2-3 weeks
- Added new Jira query for documentation tickets
- Changed Slack channel names

**2024-12-20:**
- Added risk identification section
- Updated escalation triggers
- Initial version deployed
```

**Collaborative Editing:**

If multiple people maintain the prompt:

1. Assign sections to owners
2. Use Google Doc comments for discussions
3. Review changes before deploying to production
4. Communicate updates to team

## Troubleshooting

### Agent Not Using Instructions

**Issue:** Agent doesn't follow the extended prompt

**Possible Causes:**

1. **Fetch failed:**
   - Check logs for errors
   - Verify document URL in `.env.secrets`
   - Ensure document is publicly readable

2. **Cache not invalidated:**
   - Restart services: `nox -s dev_build`
   - User hasn't re-authorized Google Drive

3. **Instructions unclear:**
   - Review wording for ambiguity
   - Add more specific examples
   - Test with specific questions

### Document Permission Issues

**Error:** "Failed to fetch extended system prompt"

**Solutions:**

1. **Check sharing settings:**
   - Open Google Doc
   - Click "Share"
   - Verify: "Anyone with the link can view" (or specific users added)

2. **Verify URL:**
   - Check `.env.secrets` has correct URL or doc ID
   - Try both full URL and just ID:
     ```bash
     # Both should work
     RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL=https://docs.google.com/document/d/1ABC123/edit
     RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL=1ABC123
     ```

3. **Check Google Drive authorization:**
   - User must have authorized Google Drive access
   - Agent will prompt if not configured

### Changes Not Appearing

**Issue:** Updated doc but agent still uses old instructions

**Solutions:**

1. **Clear cache:**
   ```bash
   nox -s dev_clean  # Clears everything
   nox -s dev_build
   ```

2. **Check correct doc:**
   - Verify you're editing the right Google Doc
   - Check `.env.secrets` points to the doc you're editing
   - Open both and compare

3. **Verify agent recreation:**
   - Agent only fetches on creation
   - Must restart services or invalidate agent cache

## FAQ

**Q: Can I use multiple prompt documents?**

A: No, configure one document per environment (dev, prod). You can have separate docs for dev and prod, but each environment uses only one.

**Q: What if I want different instructions for different users?**

A: The extended prompt is shared by all users. For user-specific behavior, you'd need code changes (different agent instances).

**Q: Can I include code in the prompt?**

A: Yes, you can include example JQL queries, markdown formatting templates, etc. But don't include Python code or agent implementation details.

**Q: How large can the prompt be?**

A: Technically up to ~50KB, but keep it concise. Long prompts can impact response time and quality. Aim for <10KB.

**Q: Can I use formatting in the Google Doc?**

A: The agent reads the raw text. Use markdown syntax (like in the template) for formatting. Google Doc formatting (bold, colors) won't transfer.

**Q: What happens if document fetch fails?**

A: Agent creation fails with an error. Set `RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL` to empty to disable (agent will work with embedded prompt only).

**Q: Can I test prompt changes without deploying?**

A: Yes! Use a dev Google Doc and point your local `.env.secrets` to it. Test locally before updating production doc.

## Getting Help

**For Prompt Content Questions:**
- Review agent responses
- Check Jira queries manually
- Test instructions step-by-step
- Get feedback from team

**For Technical Issues:**
- Check application logs: `nox -s dev_logs`
- See [CONFIGURATION.md](../CONFIGURATION.md) for setup
- See [CLAUDE.md](../../CLAUDE.md) for architecture
- File an issue in the repo

## Summary Checklist

When maintaining the prompt:

- [ ] Instructions are clear and specific
- [ ] Jira queries tested and working
- [ ] Slack channels are current
- [ ] Process timelines match reality
- [ ] Examples provided for complex formats
- [ ] No hardcoded release data
- [ ] Written for agent, not users
- [ ] Changes logged in document
- [ ] Tested before deploying to production
- [ ] Team notified of updates

---

**Remember:** The extended prompt is a powerful tool for customizing agent behavior without code changes. Keep it up to date, test your changes, and iterate based on user feedback!
