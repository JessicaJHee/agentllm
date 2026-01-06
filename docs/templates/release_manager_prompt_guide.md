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

---

## Prompt Engineering Best Practices

Before you start customizing, understand these core principles. They'll help you write effective, maintainable prompts.

### Principle 1: Explicit Tool Mapping

**Problem:** Abstract action names force the LLM to guess which tool to use.

**Bad:**
```markdown
When user asks about team issues, run **Retrieve Issues by Team** for each team.
```

**Good:**
```markdown
When user asks about team issues, use `get_issues_by_team(release_version, team_ids)` for accurate per-team counts.
```

**Why:** The agent knows exactly which function to call and what parameters it needs. No inference required.

**Action:** Always use actual function names like `get_issue()`, `get_issues_by_team()`, `get_document_content()` instead of abstract descriptions.

---

### Principle 2: DRY (Don't Repeat Yourself)

**Problem:** Duplication wastes tokens and creates ambiguity.

**Bad:**
```markdown
## Query for Feature Freeze
project IN (RHIDP, RHDHBugs) AND fixVersion = "X" and status != closed

## Query for Code Freeze
project IN (RHIDP, RHDHBugs) AND fixVersion = "X" and status != closed

## Query for Open Issues
project IN (RHIDP, RHDHBugs) AND fixVersion = "X" and status != closed
```

**Good:**
```markdown
## Query for Open Issues
project IN (RHIDP, RHDHBugs) AND fixVersion = "[RELEASE_VERSION]" and status != closed

Note: Use this query for all freeze milestones (Feature, Code, Doc)
```

**Why:** Each token counts toward context limits. Duplication = wasted space.

**Action:** Define concepts once, reference them elsewhere. Remove TODO sections and empty placeholders.

---

### Principle 3: Conciseness - Assume the LLM is Smart

**Problem:** Verbose meta-instructions about "how to think" waste tokens.

**Bad:**
```markdown
Before retrieving data:
1. Identify the data sources required for this action
2. If multiple sources exist:
   - Announce: "This action requires [Source A] (primary)..."
   - Commit: "I will check [Source A] FIRST..."
3. Execute in priority order...
```

**Good:**
```markdown
Data Sources (priority order):
1. Jira (primary) - Use `get_issue()` for release dates
2. Spreadsheet (fallback) - Only if Jira lacks dates
```

**Why:** Modern LLMs already know how to reason step-by-step. Don't teach them HOW to think, just WHAT to produce.

**Action:** Remove instructions like "announce your findings," "commit to checking X first," "verify before accessing Y." The agent does this naturally.

---

### Principle 4: Outcome-Focused Instructions

**Problem:** Procedural "do-this-then-that" steps constrain the agent's path-finding.

**Bad:**
```markdown
📋 First, gather the data:
| Step | What to Do | What You'll Get |
| 1 | Run Retrieve Release Dates | Feature Freeze date |
| 2 | Run Retrieve Teams | List of teams |
| 3 | For each team, run Retrieve Issues | Counts |

▶️ Then, fill in the template:
```

**Good:**
```markdown
**Output:** Slack message announcing Feature Freeze status

**Data Requirements:**
1. Feature Freeze date - Use `get_issue(RHDHPLAN-XXX)`
2. Active engineering teams - Use `get_document_content("DOC_ID")`
3. Team issue counts - Use `get_issues_by_team(version, ids)`

**Template:**
[actual template here]
```

**Why:** Lead with the destination (desired output), not the journey (procedure). Agents are excellent pathfinders - give them the goal and they'll optimize the route.

**Action:** Structure instructions as `Output → Data Requirements → Template`, not `Step 1 → Step 2 → Step 3 → Output`.

---

### Principle 5: Format Targeting (Destination + Delivery Method)

**Problem:** Output format must match BOTH the platform AND how it's delivered.

**Critical Discovery:** Slack has TWO formatting systems:
- **mrkdwn** (API/webhooks): `<url|text>` for links, `*bold*`
- **Markdown** (manual paste): `[text](url)` for links, `*bold*`

**Bad (assumes API):**
```markdown
• *Team* - <https://jira.com/...|71> @Lead
```
This ONLY works via API/webhooks, NOT manual pasting!

**Good (for copy-paste):**
```markdown
• *Team* - [71](https://jira.com/...) @Lead
```
This works when pasting into Slack manually.

**Why:** The `<url|text>` syntax fails when manually pasted. Users see raw angle brackets instead of links.

**Action:**
- For copy-paste workflows → Use Markdown: `[text](url)`
- For API/webhook workflows → Use mrkdwn: `<url|text>`
- Match format to delivery method, not just destination platform

**Slack Formatting Reference:**
| Format | Markdown (paste) | mrkdwn (API) |
|--------|-----------------|--------------|
| Bold | `*text*` | `*text*` |
| Link | `[text](url)` | `<url\|text>` |
| Link count | `[71](url)` | `<url\|71>` |

---

### Common Pitfalls to Avoid

**1. Empty Section Placeholders**
```markdown
❌ ## Announce Code Freeze

    (no content - TODO)
```
Remove empty sections. They waste tokens and create confusion.

**2. Mixing Formatting Syntaxes**
```markdown
❌ *RHDH 1.9.0 <url|Feature Freeze> Update*
   (mixing Markdown bold with mrkdwn link)
```
Pick ONE syntax and use it consistently.

**3. Triple-Duplicated Queries**
```markdown
❌ Same JQL query repeated under three different section names
```
Define once, reference elsewhere.

**4. Meta-Commentary About Thinking**
```markdown
❌ "Think carefully about whether Jira has the dates before checking the spreadsheet"
```
State the constraint, trust the agent to reason.

**5. Abstract Action Names Without Tool Mapping**
```markdown
❌ "Run Retrieve Issues by Team"
✅ "Use get_issues_by_team(release_version, team_ids)"
```

---

### Quick Self-Audit Checklist

Before deploying prompt changes, verify:

- [ ] **Tool mapping** - All actions use actual function names (`get_issue()`)
- [ ] **No duplication** - Each JQL query defined once
- [ ] **Concise** - No meta-instructions about how to think
- [ ] **Outcome-first** - Instructions lead with desired output
- [ ] **Format consistency** - One syntax (Markdown OR mrkdwn), not mixed
- [ ] **No empty sections** - Remove TODO placeholders
- [ ] **Tested** - Verified with actual agent before deploying

---

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
   - **Keep the markdown formatting as plain text** (see Working with Markdown below)

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
   - Copy the document URL and share with technical team for configuration

---

## Formatting Your Prompt in Google Docs

**Important:** When the technical team downloads your Google Doc, it gets converted to Markdown format (.md file) that the agent reads. You should use Google Docs' native formatting features, and they will be properly converted to the markup the agent needs.

### How It Works

**Your workflow:**
1. Edit in Google Docs using normal formatting (Bold button, heading styles, etc.)
2. Technical team downloads the document
3. Google Docs → Markdown conversion happens automatically
4. Agent reads the Markdown file

**You don't need to write Markdown syntax manually!** Use Google Docs like you normally would.

### Google Docs Formatting → Markdown Conversion

Here's how your Google Docs formatting converts to agent-readable markup:

| What You Do in Google Docs | What Agent Receives | How To Do It |
|---------------------------|---------------------|--------------|
| **Heading 1** (title style) | `# Heading 1` | Format → Paragraph styles → Title or Heading 1 |
| **Heading 2** (subtitle) | `## Heading 2` | Format → Paragraph styles → Heading 2 |
| **Heading 3** | `### Heading 3` | Format → Paragraph styles → Heading 3 |
| **Bold text** | `**bold text**` | Ctrl+B / Cmd+B or Bold button |
| **Italic text** | `*italic text*` | Ctrl+I / Cmd+I or Italic button |
| **Hyperlink** | `[text](url)` | Ctrl+K / Cmd+K or Insert → Link |
| Bullet list | `- item` | Bullet list button |
| Numbered list | `1. item` | Numbered list button |
| **Code block** | ` ```code``` ` | Type `@` then "Code blocks" OR Insert → Building blocks → Code blocks |
| Inline code | `` `code` `` | Courier New font (or enable Markdown and use backticks) |

### Best Practices for Clean Conversion

**1. Use Heading Styles for Structure**

✅ **DO:** Use "Heading 1", "Heading 2", "Heading 3" from the styles dropdown
- Ensures consistent hierarchy
- Converts cleanly to `#`, `##`, `###`

❌ **DON'T:** Make text bigger and bold manually
- Inconsistent conversion
- Agent may not recognize as headings

**2. Use Hyperlinks Properly**

✅ **DO:** Select text, press Ctrl+K, paste URL
- Converts to `[text](url)` format
- Links work in agent output

❌ **DON'T:** Paste raw URLs without link text
- Harder to read
- Less semantic meaning

**Example:**
```
Good: "See the [RHDH Release Process](https://docs.google.com/..."
Bad:  "See https://docs.google.com/document/d/13OkypJ3u..."
```

**3. Format Code Blocks**

For JQL queries, code snippets, or command examples, Google Docs has **native code block support**:

✅ **DO (Recommended - Native Code Blocks):**
1. Type `@` and select "Code blocks" from the menu
2. OR use menu: Insert → Building blocks → Code blocks
3. Paste your code into the code block
4. Optionally select a programming language for syntax highlighting

**Alternative (Manual formatting):**
1. Type or paste the code
2. Select it
3. Change font to "Courier New" or "Consolas"

**Example in Google Docs:**
```
Query for open issues:

[Insert code block here with @ > Code blocks]
project = RHDH AND fixVersion = "1.5.0"
```

**💡 Tip:** You can also enable Markdown support in Google Docs (Tools → Preferences → "Automatically detect Markdown"), which lets you use triple backticks (```) for code blocks.

**4. Use Lists Consistently**

✅ **DO:** Use the bullet list or numbered list buttons
- Clean conversion to Markdown
- Proper indentation

❌ **DON'T:** Type dashes or numbers manually
- Inconsistent formatting
- May not convert properly

### Practical Examples

**Example 1: Creating a Section with Instructions**

**In Google Docs, you type:**
```
Heading 2 style: "Retrieve Release Dates"

Normal text: "Output: Table of release versions with critical dates"

Bold: "Data Sources (priority order):"
1. Jira (numbered list)
2. Release Schedule Spreadsheet (numbered list)

Normal text: "Check Jira first using" (then monospace:) get_issue()
```

**Agent receives (after conversion):**
```markdown
## Retrieve Release Dates

**Output:** Table of release versions with critical dates

**Data Sources (priority order):**
1. Jira
2. Release Schedule Spreadsheet

Check Jira first using `get_issue()`
```

**Example 2: Adding a JQL Query**

**In Google Docs:**
```
Normal text: "Query for open issues:"

Code formatting (Courier New, indented):
project = RHDH AND fixVersion = "[RELEASE_VERSION]" AND status != closed
```

**Agent receives:**
```markdown
Query for open issues:

```
project = RHDH AND fixVersion = "[RELEASE_VERSION]" AND status != closed
```
```

### Common Issues and Solutions

**Issue 1: Headings not converting properly**

**Problem:** Text looks like a heading but doesn't convert
**Solution:** Use Format → Paragraph styles → Heading 1/2/3 (don't just make text bigger and bold)

**Issue 2: Links showing as raw URLs**

**Problem:** Agent sees `https://...` instead of `[text](url)`
**Solution:** Always use Insert → Link (Ctrl+K) to create hyperlinks with descriptive text

**Issue 3: Code not formatting correctly**

**Problem:** JQL queries or code snippets break the formatting
**Solution:**
1. Select the code
2. Change font to Courier New or Consolas
3. Keep it in its own paragraph

**Issue 4: Lists not indenting properly**

**Problem:** Nested lists don't convert correctly
**Solution:** Use the "Increase indent" button (Tab key) for nested items, not manual spaces

### Document Settings for Best Results

**Recommended settings:**

1. **Enable Markdown support** (optional but helpful):
   - Tools → Preferences
   - Check "Automatically detect Markdown"
   - Allows you to use triple backticks (```) for code blocks and other shortcuts

2. **Turn off smart quotes:**
   - Tools → Preferences
   - Uncheck "Use smart quotes"
   - This prevents curly quotes that may not convert well

3. **Font:** Use "Arial" or "Roboto" for body text, code blocks handle code automatically

4. **Spacing:** Use "Normal" line spacing (1.15 or single)

### Quick Reference

**Format Text:**
- Headings: Format menu → Paragraph styles
- Bold: Ctrl+B / Cmd+B
- Italic: Ctrl+I / Cmd+I
- Code blocks: Type `@` → "Code blocks" (recommended)
- Links: Ctrl+K / Cmd+K

**Structure Content:**
- Use heading hierarchy (H1 → H2 → H3)
- Use lists for enumeration
- Use links for references
- Use code blocks for JQL queries and code examples

**Pro Tips:**
- Enable Markdown: Tools → Preferences → "Automatically detect Markdown"
- Use `@` menu for quick access to building blocks
- Turn off smart quotes to avoid conversion issues

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
   - Open your Google Doc
   - Make changes using Markdown syntax (see "Working with Markdown" section)
   - Save automatically (Google Docs saves as you type)

2. **Changes take effect:**
   - Changes are live immediately in the Google Doc
   - The agent will use updated content when it refreshes
   - Coordinate with your technical team if changes need immediate application

### Testing Updates

**Best Practice: Use a Dev Copy**

1. **Create dev copy:**
   - In Google Drive, right-click your production doc
   - Select "Make a copy"
   - Name it: "Release Manager System Prompt - DEV"

2. **Make and test changes:**
   - Edit the dev doc with your proposed changes
   - Share dev doc URL with technical team for testing
   - Ask technical team to verify agent behavior with dev doc

3. **Deploy to production:**
   - Once testing confirms changes work correctly
   - Copy the updated content from dev doc to production doc
   - Production agent will use new content on next refresh

**Quick Edits (for minor changes):**

If you're fixing typos or updating dates:
1. Edit production doc directly
2. Changes are live immediately
3. Monitor agent responses to ensure no issues

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

### Example 5: Add Freeze-Specific Query Overrides

**Scenario:** You need different JIRA queries for Feature Freeze vs Code Freeze announcements.

**Update Tool Documentation:**

In the "Available Tools" section, document the `base_jql` parameter:

```markdown
### Jira Tools

- **`get_issues_by_team(release_version, team_ids, base_jql=None)`** - Get accurate per-team issue counts. Optional `base_jql` parameter overrides default query for different freeze types.
```

**Add Freeze-Specific Instructions:**

In the "Actions" section, add query override examples:

```markdown
## Announce Feature Freeze Update

**Data Requirements:**
3. Team issue counts - Use `get_issues_by_team(release_version, team_ids)` for accurate counts
   (Uses default: `project IN (...) AND status != closed`)

## Announce Code Freeze Update

**Data Requirements:**
3. Team issue counts - Use `get_issues_by_team()` with **code freeze query override**

**Query Override for Code Freeze:**

\```python
get_issues_by_team(
    release_version,
    team_ids,
    base_jql="project IN (RHIDP, RHDHBugs, RHDHPLAN, RHDHSUPP) AND status NOT IN (closed, verified)"
)
\```
```

**Why this approach works:**
- Default query handles Feature Freeze automatically
- Override parameter enables custom filtering for Code Freeze (or other milestones)
- Queries live in the prompt (Google Doc), not code - easy to iterate
- Release managers can adjust the status filter without needing code changes

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


## Troubleshooting

### Agent Not Using My Instructions

**Issue:** Agent doesn't follow the extended prompt

**What You Can Check:**

1. **Verify document sharing:**
   - Open your Google Doc
   - Click "Share" button
   - Ensure "Anyone with the link can view" is enabled
   - OR ensure specific technical team members have access

2. **Check instructions clarity:**
   - Review your wording for ambiguity
   - Add more specific examples
   - Use concrete function names (e.g., `get_issue()`)
   - Follow the "Quick Self-Audit Checklist" above

3. **Contact technical team:**
   - Share the specific agent behavior you're seeing
   - Provide the doc URL
   - Ask them to verify the agent is reading your doc

### Document Permission Issues

**Symptom:** Technical team reports "Failed to fetch extended system prompt"

**What You Can Do:**

1. **Fix sharing settings:**
   - Open Google Doc
   - Click "Share" button
   - Change to "Anyone with the link can view"
   - OR add the service account email provided by technical team

2. **Verify you're sharing the right link:**
   - Copy the document URL from your browser
   - It should look like: `https://docs.google.com/document/d/LONG_ID_HERE/edit`
   - Share this exact URL with technical team

### Changes Not Appearing

**Issue:** You updated the doc but agent still uses old instructions

**What You Can Do:**

1. **Verify you're editing the right doc:**
   - Ask technical team which doc URL is configured
   - Open that doc and confirm it has your changes
   - Check you're not accidentally editing a copy

2. **Check for Markdown errors:**
   - Copy a section of your doc
   - Paste into https://markdownlivepreview.com/
   - Verify formatting renders correctly
   - Fix any syntax errors

3. **Request cache refresh:**
   - Contact technical team
   - Ask them to refresh the agent's cache
   - Provide doc URL and what you changed

## FAQ

**Q: Can I use Google Docs formatting (bold, headings, etc.)?**

A: Yes! Use Google Docs normally. When the document is downloaded, your formatting converts to Markdown automatically. Use the Bold button (Ctrl+B), heading styles, and Insert Link (Ctrl+K) as you normally would. See "Formatting Your Prompt in Google Docs" section.

**Q: How do I make headings?**

A: Use Google Docs' built-in heading styles:
- Format → Paragraph styles → Heading 1
- Format → Paragraph styles → Heading 2
- Format → Paragraph styles → Heading 3

These convert to the proper Markdown format automatically when downloaded.

**Q: How do I make links?**

A: Use Google Docs' link feature:
1. Select the text you want to link
2. Press Ctrl+K (or Cmd+K on Mac)
3. Paste the URL
4. Click "Apply"

This converts to `[text](url)` format when the document is downloaded.

**Q: Can I include code (like JQL queries)?**

A: Yes! Google Docs has native code block support:
1. Type `@` and select "Code blocks" (easiest method)
2. OR use Insert → Building blocks → Code blocks
3. Paste your code into the code block

Alternative: Select text and change font to "Courier New"

**Bonus tip:** Enable Markdown in Tools → Preferences → "Automatically detect Markdown", then you can use triple backticks (```) for code blocks.

When downloaded, code blocks convert to proper Markdown code formatting.

**Q: How large can the prompt be?**

A: Keep it concise - aim for under 10KB (roughly 20-30 Google Docs pages). Long prompts can slow agent responses and reduce quality. Follow the "Conciseness" principle.

**Q: What if I want different instructions for different users?**

A: The prompt is shared by all users. Everyone using the agent sees the same instructions. For user-specific behavior, contact your technical team.

**Q: Can I test changes before they go live?**

A: Yes! Make a copy of the production doc, edit the copy, and share it with your technical team for testing. Once verified, copy the changes to the production doc.

**Q: Do my changes take effect immediately?**

A: Changes are saved immediately in Google Docs, but the agent may cache the prompt. For important changes, notify your technical team so they can refresh the cache.

## Getting Help

**For Prompt Content Questions:**
- Test Jira queries manually in Jira first
- Review the "Quick Self-Audit Checklist" above
- Check that formatting looks clean in Google Docs
- Get feedback from team members who use the agent

**For Technical Issues:**
- Contact your technical team
- Provide: doc URL, what you changed, and what behavior you're seeing
- They can check logs and configuration

## Summary Checklist

When maintaining the prompt:

**Content Quality:**
- [ ] Instructions are clear and specific
- [ ] Jira queries tested manually in Jira first
- [ ] Slack channels are current
- [ ] Process timelines match reality
- [ ] Examples provided for complex formats
- [ ] No hardcoded release data
- [ ] Written for agent, not users

**Google Docs Formatting:**
- [ ] Used heading styles (Format → Paragraph styles → Heading 1/2/3)
- [ ] Used Bold button (Ctrl+B) for emphasis
- [ ] Used Insert Link (Ctrl+K) for hyperlinks with descriptive text
- [ ] Used code blocks (@ → "Code blocks") for JQL queries and code examples
- [ ] Used list buttons for bullet/numbered lists (not manual dashes)
- [ ] Optionally enabled Markdown support (Tools → Preferences)

**Best Practices:**
- [ ] Followed "Quick Self-Audit Checklist" (7 points above)
- [ ] No duplicate queries or empty sections
- [ ] Used actual function names (`get_issue()`)
- [ ] Outcome-focused structure (Output → Data → Template)

**Deployment:**
- [ ] Changes logged in document
- [ ] Tested in dev copy before production
- [ ] Team notified of updates
- [ ] Technical team contacted for cache refresh (if needed)

---

**Remember:** The extended prompt is a powerful tool for customizing agent behavior. Keep it concise, use Markdown correctly, test your changes, and iterate based on user feedback!
