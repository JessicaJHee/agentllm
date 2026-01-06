"""
Jira toolkit for interacting with Jira issues and projects.
"""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from agno.tools import Toolkit
from loguru import logger
from pydantic import BaseModel, Field

try:
    from jira import JIRA, Issue
except ImportError:
    raise ImportError("`jira` not installed. Please install using `pip install jira`") from None


class JiraCommentData(BaseModel):
    """Pydantic model for Jira comment data."""

    id: str | None = Field(None, description="Comment ID")
    author: str = Field(..., description="Comment author display name")
    created: str = Field(..., description="Comment creation timestamp")
    body: str = Field(..., description="Comment body text")
    pr_urls_found: list[str] = Field(default_factory=list, description="GitHub PR URLs found in comment")


class JiraIssueData(BaseModel):
    """Pydantic model for Jira issue data."""

    key: str = Field(..., description="Jira ticket key (e.g., PROJ-123)")
    summary: str = Field(..., description="Ticket summary/title")
    description: str = Field(..., description="Ticket description content")
    status: str = Field(..., description="Current ticket status")
    priority: str = Field(..., description="Priority level of the ticket")
    assignee: str | None = Field(None, description="Assigned user display name")
    reporter: str | None = Field(None, description="Reporter user display name")
    created_date: str | None = Field(None, description="Ticket creation timestamp")
    updated_date: str | None = Field(None, description="Last update timestamp")
    components: list[str] = Field(default_factory=list, description="Affected components")
    labels: list[str] = Field(default_factory=list, description="Ticket labels")
    target_version: list[str] | None = Field(None, description="Target version(s) for the issue")
    product_manager: str | None = Field(None, description="Product manager display name")
    pull_requests: list[str] = Field(default_factory=list, description="GitHub PR URLs found in ticket")
    comments: list[JiraCommentData] | None = Field(None, description="All ticket comments with PR URLs extracted")
    custom_fields: dict[str, Any] | None = Field(None, description="Custom Jira fields like release notes")


def parse_json_to_jira_issue(json_content: str) -> JiraIssueData | None:
    """
    Parse JSON content into a JiraIssueData object.

    Args:
        json_content: JSON string containing Jira issue data

    Returns:
        JiraIssueData object if parsing successful, None otherwise
    """
    try:
        data = json.loads(json_content)
        logger.debug("Parsing JSON content to JiraIssueData", data=data)

        # Handle different possible JSON structures
        if isinstance(data, dict):
            # Extract fields that match JiraIssueData structure
            issue_data = {
                "key": data.get("key", ""),
                "summary": data.get("summary", data.get("title", "")),
                "description": data.get("description", ""),
                "status": data.get("status", "Unknown"),
                "priority": data.get("priority", "Unknown"),
                "assignee": data.get("assignee"),
                "reporter": data.get("reporter"),
                "created_date": data.get("created_date"),
                "updated_date": data.get("updated_date"),
                "components": data.get("components", []),
                "labels": data.get("labels", []),
                "pull_requests": data.get("pull_requests", []),
                "comments": data.get("comments"),
                "custom_fields": data.get("custom_fields"),
            }

            return JiraIssueData(**issue_data)

    except Exception as e:
        logger.error(f"Failed to parse JSON to JiraIssueData: {e}")
        return None

    return None


class JiraTools(Toolkit):
    """Toolkit for interacting with Jira issues, projects, and comments."""

    def __init__(
        self,
        token: str,
        server_url: str,
        username: str | None = None,
        default_base_jql: str = "",
        get_issue: bool = True,
        get_issues_detailed: bool = True,
        get_issues_stats: bool = True,
        get_issues_summary: bool = True,
        get_fix_versions: bool = True,
        get_issues_by_team: bool = True,
        add_comment: bool = False,
        create_issue: bool = False,
        extract_sprint_info: bool = True,
        get_sprint_metrics: bool = True,
        update_issue: bool = False,
        **kwargs,
    ):
        """Initialize Jira toolkit with credentials.

        Args:
            token: Jira personal access token
            server_url: Jira server URL
            username: Optional username for basic auth
            default_base_jql: Default JQL base query (e.g., "project IN (FOO) AND status != closed")
                Applied to queries that need base scoping. Empty string means no filter.
            get_issue: Include get_issue tool (default: True)
            get_issues_detailed: Include get_issues_detailed tool (default: True)
            get_issues_stats: Include get_issues_stats tool (default: True)
            get_issues_summary: Include get_issues_summary tool (default: True)
            get_fix_versions: Include get_fix_versions tool (default: True)
            get_issues_by_team: Include get_issues_by_team tool (default: True)
            add_comment: Include add_comment tool (default: False)
            create_issue: Include create_issue tool (default: False)
            extract_sprint_info: Include extract_sprint_info tool (default: True)
            get_sprint_metrics: Include get_sprint_metrics tool (default: True)
            update_issue: Include update_issue tool (default: False)
            **kwargs: Additional arguments passed to parent Toolkit
        """
        self._token = token
        self._server_url = server_url
        self._username = username
        self._default_base_jql = default_base_jql

        self._jira_client: JIRA | None = None

        tools: list[Any] = []
        if get_issue:
            tools.append(self.get_issue)
        if get_issues_stats:
            tools.append(self.get_issues_stats)
        if get_issues_summary:
            tools.append(self.get_issues_summary)
        if get_fix_versions:
            tools.append(self.get_fix_versions)
        if get_issues_detailed:
            tools.append(self.get_issues_detailed)
        if get_issues_by_team:
            tools.append(self.get_issues_by_team)
        if add_comment:
            tools.append(self.add_comment)
        if create_issue:
            tools.append(self.create_issue)
        if extract_sprint_info:
            tools.append(self.extract_sprint_info)
        if get_sprint_metrics:
            tools.append(self.get_sprint_metrics)
        if update_issue:
            tools.append(self.update_issue)

        super().__init__(name="jira_tools", tools=tools, **kwargs)

    def validate_connection(self) -> tuple[bool, str]:
        """Validate the Jira connection by making a simple API call.

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            logger.debug(f"Validating Jira connection to {self._server_url}")
            jira = self._get_jira_client()

            # Try to get current user info as a simple validation
            user = jira.myself()
            username = user.get("displayName", user.get("name", "Unknown"))

            logger.info(f"Successfully connected to Jira as {username}")
            return True, f"Successfully connected to Jira as {username}"
        except Exception as e:
            error_msg = f"Failed to connect to Jira: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

    def _get_jira_client(self) -> JIRA:
        """Get or create JIRA client instance using stored credentials."""
        if self._jira_client is None:
            logger.debug(f"Initializing JIRA client with server_url: {self._server_url}")
            logger.debug(f"Username provided: {'Yes' if self._username else 'No'}")
            logger.debug("Token provided: Yes")

            if not self._server_url:
                raise ValueError("server_url is required")

            if not self._token:
                raise ValueError("token is required")

            logger.debug(f"Connecting to Jira at {self._server_url}")

            try:
                if self._username and self._token:
                    logger.debug("Using basic auth (username + token)")
                    self._jira_client = JIRA(
                        server=self._server_url,
                        basic_auth=(self._username, self._token),
                    )
                else:
                    logger.debug("Using token auth")
                    self._jira_client = JIRA(server=self._server_url, token_auth=self._token)

                logger.debug("Successfully created JIRA client")
            except Exception as e:
                logger.error(f"Failed to create JIRA client: {e}")
                raise

        return self._jira_client

    def _extract_github_pr_urls(self, text: str) -> list[str]:
        """Extract GitHub PR URLs from text.

        Args:
            text: Text to search for GitHub PR URLs

        Returns:
            List of GitHub PR URLs found in the text
        """
        if not text:
            return []

        # Pattern to match GitHub PR URLs
        pattern = r"https://github\.com/[^/\s]+/[^/\s]+/pull/\d+"
        matches = re.findall(pattern, text, re.IGNORECASE)

        return list(set(matches))  # Remove duplicates

    def _format_issue_details(self, issue: Issue) -> JiraIssueData:
        """
        Format JIRA issue details into a structured JiraIssueData object.

        Args:
            issue: JIRA Issue object

        Returns:
            JiraIssueData object with formatted issue details
        """
        logger.debug(f"Formatting issue details for {issue.key}")

        # Extract basic fields
        details = {
            "key": issue.key,
            "summary": issue.fields.summary,
            "description": issue.fields.description or "",
            "status": issue.fields.status.name,
            "priority": (issue.fields.priority.name if issue.fields.priority else "Unknown"),
            "assignee": (issue.fields.assignee.displayName if issue.fields.assignee else None),
            "reporter": (issue.fields.reporter.displayName if issue.fields.reporter else None),
            "created_date": str(issue.fields.created) if issue.fields.created else None,
            "updated_date": str(issue.fields.updated) if issue.fields.updated else None,
            "components": ([comp.name for comp in issue.fields.components] if issue.fields.components else []),
            "labels": list(issue.fields.labels) if issue.fields.labels else [],
        }

        logger.debug(f"Basic fields extracted for {issue.key}: {len(details)} fields")

        # Extract GitHub PR URLs from description
        pr_urls = self._extract_github_pr_urls(details["description"])
        logger.debug(f"Found {len(pr_urls)} PR URLs in description")

        # Extract comments and their content for PR URLs
        comments_data = []
        try:
            if hasattr(issue.fields, "comment") and hasattr(issue.fields.comment, "comments"):
                comments = issue.fields.comment.comments
                logger.debug(f"Processing {len(comments)} comments for {issue.key}")

                for comment in comments:
                    if hasattr(comment, "body") and comment.body:
                        comment_pr_urls = self._extract_github_pr_urls(comment.body)
                        pr_urls.extend(comment_pr_urls)

                        # Store comment data using Pydantic model
                        comment_data = JiraCommentData(
                            id=getattr(comment, "id", None),
                            author=getattr(getattr(comment, "author", {}), "displayName", "Unknown"),
                            created=str(getattr(comment, "created", "")),
                            body=comment.body,
                            pr_urls_found=comment_pr_urls,
                        )
                        comments_data.append(comment_data)

                        if comment_pr_urls:
                            logger.debug(f"Found {len(comment_pr_urls)} PR URLs in comment {comment.id}")
            else:
                logger.debug(f"No comments found for {issue.key}")
        except (AttributeError, Exception) as e:
            logger.debug(f"Could not extract comments from issue {issue.key}: {e}")

        # Check for custom PR field (customfield_12310220)
        pr_data = None
        try:
            pr_data = getattr(issue.fields, "customfield_12310220", None)
            logger.debug(f"Custom PR field data for {issue.key}: {pr_data}")

            if pr_data:
                if isinstance(pr_data, list) and pr_data:
                    # If it's a list, process each element
                    for item in pr_data:
                        if isinstance(item, str) and item.startswith("https://github.com"):
                            pr_urls.append(item)
                            logger.debug(f"Found PR URL in custom field list: {item}")
                elif isinstance(pr_data, str) and pr_data.startswith("https://github.com"):
                    pr_urls.append(pr_data)
                    logger.debug(f"Found PR URL in custom field: {pr_data}")
        except (AttributeError, Exception) as e:
            logger.debug(f"Could not extract custom PR field from issue {issue.key}: {e}")

        # Extract target version (customfield_12319940)
        target_version = None
        try:
            target_version_data = getattr(issue.fields, "customfield_12319940", None)
            if target_version_data:
                if isinstance(target_version_data, list):
                    # Extract version names from version objects
                    target_version = [v.name if hasattr(v, "name") else str(v) for v in target_version_data]
                    logger.debug(f"Found target version(s) for {issue.key}: {target_version}")
                else:
                    # Single version object
                    target_version = [target_version_data.name if hasattr(target_version_data, "name") else str(target_version_data)]
                    logger.debug(f"Found single target version for {issue.key}: {target_version}")
        except (AttributeError, Exception) as e:
            logger.debug(f"Could not extract target version from issue {issue.key}: {e}")

        # Extract product manager (customfield_12316752)
        product_manager = None
        try:
            product_manager_data = getattr(issue.fields, "customfield_12316752", None)
            if product_manager_data:
                if hasattr(product_manager_data, "displayName"):
                    product_manager = product_manager_data.displayName
                    logger.debug(f"Found product manager for {issue.key}: {product_manager}")
                elif isinstance(product_manager_data, str):
                    product_manager = product_manager_data
                    logger.debug(f"Found product manager (string) for {issue.key}: {product_manager}")
        except (AttributeError, Exception) as e:
            logger.debug(f"Could not extract product manager from issue {issue.key}: {e}")

        # Add custom fields section for additional metadata
        custom_fields = {}
        try:
            # Epic Link (customfield_12311140)
            epic_link = getattr(issue.fields, "customfield_12311140", None)
            if epic_link:
                custom_fields["epic_link"] = epic_link
                logger.debug(f"Found Epic Link for {issue.key}: {epic_link}")

            # Release note text (customfield_12317313)
            release_note_text = getattr(issue.fields, "customfield_12317313", None)
            if release_note_text:
                custom_fields["release_note_text"] = release_note_text
                logger.debug(f"Found release note text for {issue.key}")

            # Release note status (customfield_12310213)
            release_note_status = getattr(issue.fields, "customfield_12310213", None)
            if release_note_status:
                if hasattr(release_note_status, "get"):
                    status_value = release_note_status.get("value")
                else:
                    status_value = str(release_note_status)
                custom_fields["release_note_status"] = status_value
                logger.debug(f"Found release note status for {issue.key}: {status_value}")

            # PR data field (customfield_12310220)
            if pr_data:
                custom_fields["pr_data"] = pr_data
                logger.debug(f"Added PR data to custom fields for {issue.key}")

            # Log all available custom fields for debugging
            all_custom_fields = []
            for field_name in dir(issue.fields):
                if field_name.startswith("customfield_"):
                    field_value = getattr(issue.fields, field_name, None)
                    if field_value is not None:
                        all_custom_fields.append(field_name)

            if all_custom_fields:
                logger.debug(f"Available custom fields for {issue.key}: {all_custom_fields}")

        except (AttributeError, Exception) as e:
            logger.debug(f"Could not extract custom fields from issue {issue.key}: {e}")

        # Create and return JiraIssueData object
        issue_data = JiraIssueData(
            key=details["key"],
            summary=details["summary"],
            description=details["description"],
            status=details["status"],
            priority=details["priority"],
            assignee=details["assignee"],
            reporter=details["reporter"],
            created_date=details["created_date"],
            updated_date=details["updated_date"],
            components=details["components"],
            labels=details["labels"],
            target_version=target_version,
            product_manager=product_manager,
            pull_requests=list(set(pr_urls)),  # Remove duplicates
            comments=comments_data if comments_data else None,
            custom_fields=custom_fields if custom_fields else None,
        )

        logger.debug(f"Finished formatting issue details for {issue.key}")
        logger.debug(f"Total unique PR URLs found for {issue.key}: {len(issue_data.pull_requests)}")

        return issue_data

    def get_issue(self, issue_key: str, include_all_comments: bool = True) -> str:
        """Retrieve detailed information about a Jira issue.

        Args:
            issue_key: The key of the issue to retrieve (e.g., PROJ-123)
            include_all_comments: Whether to fetch all comments (default: True)

        Returns:
            JSON string containing detailed issue information including GitHub PR
            links and all comments
        """
        try:
            logger.debug(f"Starting to retrieve issue {issue_key}")
            jira = self._get_jira_client()

            # Expand comments and changelog to get full issue data
            logger.debug(f"Fetching issue {issue_key} with comments and changelog expansion")
            issue = jira.issue(issue_key, expand="renderedFields,changelog,comments")

            logger.debug(f"Successfully fetched issue {issue_key}")

            # If we want all comments and the issue has comments, fetch them separately
            # This ensures we get all comments, not just the default limited set
            if include_all_comments and hasattr(issue.fields, "comment"):
                try:
                    logger.debug(f"Fetching all comments for {issue_key}")
                    all_comments = jira.comments(issue_key)
                    logger.debug(f"Retrieved {len(all_comments)} comments for {issue_key}")

                    # Replace the limited comments with all comments
                    issue.fields.comment.comments = all_comments
                    logger.debug(f"Updated issue with all {len(all_comments)} comments")
                except Exception as e:
                    logger.warning(f"Could not fetch all comments for {issue_key}: {e}")
                    # Continue with the comments we have from the original fetch

            issue_details = self._format_issue_details(issue)

            logger.debug(f"Retrieved issue details for {issue_key}")
            logger.debug(f"Found {len(issue_details.pull_requests)} PR URLs")
            logger.debug(f"Total comments processed: {len(issue_details.comments or [])}")

            return json.dumps(issue_details.model_dump(), indent=2)

        except Exception as e:
            error_msg = f"Error retrieving issue {issue_key}: {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": str(e)})

    def get_issues_stats(self, jql_query: str) -> str:
        """Get issue statistics with breakdown by type, status, and priority.

        This is a lightweight tool optimized for statistics - it returns ONLY metadata,
        no issue details. Use this when you need counts and breakdowns without listing issues.

        **IMPORTANT**:
        - `total_count` is ALWAYS accurate (no sampling)
        - Breakdowns (`by_type`, `by_status`, `by_priority`) are based on a SAMPLE of up to 100 issues
        - If total > 100, the breakdowns are approximate proportions, not exact counts
        - For accurate team-based counts, use `get_issues_by_team()` instead

        Args:
            jql_query: JQL query string to count issues

        Returns:
            JSON string containing ONLY summary metadata:
            - total_count: Total number of matching issues (ALWAYS ACCURATE)
            - by_type: Count breakdown by issue type (SAMPLE-BASED if total > 100)
            - by_status: Count breakdown by status (SAMPLE-BASED if total > 100)
            - by_priority: Count breakdown by priority (SAMPLE-BASED if total > 100)
            - query: The JQL query that was executed

        Example response:
            {
              "total_count": 33,
              "by_type": {"Feature": 33},
              "by_status": {"Backlog": 7, "In Progress": 14, "New": 10, "Refinement": 2},
              "by_priority": {"Major": 16, "Critical": 8, "Normal": 8, "Blocker": 1},
              "query": "issuetype = Feature AND fixVersion = \"1.9.0\" AND labels = demo"
            }
        """
        # Fetch up to 100 issues to calculate breakdowns
        # This is a balance between accuracy and performance
        result_json = self.get_issues_detailed(
            jql_query=jql_query,
            fields="key,type,status,priority",  # Minimal fields needed for breakdowns
            max_results=100,  # Fetch sample for breakdowns
            include_summary=True,
        )

        result = json.loads(result_json)

        # Return ONLY the summary
        return json.dumps(
            {
                "total_count": result["summary"]["total_count"],
                "by_type": result["summary"]["by_type"],
                "by_status": result["summary"]["by_status"],
                "by_priority": result["summary"]["by_priority"],
                "query": result["query"],
            },
            indent=2,
        )

    def get_fix_versions(self, jql_query: str, max_results: int = 10) -> str:
        """Get unique fix versions from issues matching a JQL query.

        This is a lightweight tool optimized for extracting fix versions without
        fetching full issue details. Use this when you need to identify release
        versions (e.g., "What's the current release?").

        Args:
            jql_query: JQL query string to search for issues
            max_results: Maximum number of issues to query (default: 10)
                        Higher values ensure you capture all unique versions

        Returns:
            JSON string containing:
            - fix_versions: List of unique fix version names in descending order
            - total_issues_queried: Number of issues examined
            - query: The JQL query that was executed

        Example response:
            {
              "fix_versions": ["1.9.0", "1.8.1", "1.8.0"],
              "total_issues_queried": 10,
              "query": "project in (RHIDP, RHDHBugs) AND fixVersion in unreleasedVersions() ORDER BY fixVersion DESC"
            }
        """
        try:
            logger.debug(f"Getting fix versions with JQL: {jql_query}")
            logger.debug(f"Max results: {max_results}")

            jira = self._get_jira_client()

            # Fetch minimal issue data (just fixVersions field)
            logger.debug("Executing JQL search for fix versions")
            issues = jira.search_issues(jql_query, maxResults=max_results, fields="fixVersions")

            logger.debug(f"Found {len(issues)} issues")

            # Extract unique fix versions
            fix_versions_set = set()
            for issue in issues:
                if hasattr(issue.fields, "fixVersions") and issue.fields.fixVersions:
                    for version in issue.fields.fixVersions:
                        if hasattr(version, "name"):
                            fix_versions_set.add(version.name)
                            logger.debug(f"Found fix version: {version.name} in issue {issue.key}")

            # Sort versions in descending order (newest first)
            fix_versions_list = sorted(fix_versions_set, reverse=True)

            logger.debug(f"Extracted {len(fix_versions_list)} unique fix versions")

            result = {
                "fix_versions": fix_versions_list,
                "total_issues_queried": len(issues),
                "query": jql_query,
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            error_msg = f"Error getting fix versions with JQL '{jql_query}': {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})

    def get_issues_summary(self, jql_query: str, max_results: int = 50) -> str:
        """Get Jira issues with minimal fields (key, summary, status).

        This is optimized for listing issues when you don't need full details.
        Includes summary metadata for context. Use this for "Show me...", "List..." queries.

        **PAGINATION WARNING**: Returns at most `max_results` issues (default: 50).
        Check `summary.has_more` and use `summary.total_count` for accurate totals.
        For team-based breakdowns, use `get_issues_by_team()` instead.

        Args:
            jql_query: JQL query string to search for issues
            max_results: Maximum number of results to return (default: 50, max: 1000)

        Returns:
            JSON string containing:
            - summary: Metadata (total_count is always accurate, breakdowns are sample-based)
            - issues: List with only key, summary, status fields (up to max_results)
            - query: The JQL query that was executed
        """
        return self.get_issues_detailed(
            jql_query=jql_query,
            fields="key",  # Only key, summary, status (always included)
            max_results=max_results,
            include_summary=True,
        )

    def get_issues_detailed(
        self,
        jql_query: str,
        fields: str = "key,summary,status,type,assignee,priority,components,labels",
        max_results: int = 50,
        include_summary: bool = True,
    ) -> str:
        """Get detailed Jira issue information using a JQL query with custom field selection.

        **PAGINATION WARNING**: This tool returns at most `max_results` issues (default: 50).
        Check `summary.has_more` to see if there are more results. The `summary.total_count`
        always shows the accurate total, but `issues` array and breakdown stats (`by_type`,
        `by_status`, `by_priority`) are based on the returned sample only.

        **For accurate counts across all issues**, use:
        - `get_issues_stats()` - Get total count with breakdowns
        - `get_issues_by_team()` - Get accurate team breakdown without pagination
        - Increase `max_results` (up to 1000) if you need more issues

        Args:
            jql_query: JQL query string to search for issues
            fields: Comma-separated list of fields to return. Available fields:
                   - key, summary, status, type (always included)
                   - assignee, priority, components, labels (standard fields)
                   - created_date, updated_date (timestamps)
                   - target_version, product_manager, epic_link, pr_data,
                     release_note_text, release_note_status (custom fields)
                   Default: "key,summary,status,type,assignee,priority,components,labels"
            max_results: Maximum number of results to return (default: 50, max: 1000)
            include_summary: Include summary metadata (total count, breakdown by status/type/priority).
                           Default: True

        Returns:
            JSON string containing:
            - summary: Metadata about the search results (if include_summary=True)
              - total_count: Accurate total (always correct regardless of pagination)
              - returned_count: Number of issues in this response
              - has_more: True if there are more results beyond max_results
              - by_type/by_status/by_priority: Breakdowns (sample-based if has_more=true)
            - issues: List of matching issues with requested fields (up to max_results)
            - query: The JQL query that was executed
        """
        try:
            logger.debug(f"Starting search with JQL: {jql_query}")
            logger.debug(f"Max results: {max_results}, fields: {fields}, include_summary: {include_summary}")

            # Parse requested fields
            requested_fields = [f.strip() for f in fields.split(",")]
            logger.debug(f"Requested fields: {requested_fields}")

            jira = self._get_jira_client()

            # First, get total count with maxResults=0 for accurate summary
            logger.debug("Getting total count for summary")
            start_time = time.time()
            # Use json_result=True to avoid fetching all issues (30x faster!)
            count_result = jira.search_issues(jql_query, maxResults=0, json_result=True)
            total_count = count_result.get("total", 0)
            elapsed = time.time() - start_time
            logger.info(f"Count query completed in {elapsed:.2f}s - Total: {total_count}")

            # Now fetch the actual issues up to max_results
            logger.info(f"Fetching {max_results} issues with expanded fields (changelog)")
            start_time = time.time()
            issues = jira.search_issues(jql_query, maxResults=max_results, expand="renderedFields,changelog")
            elapsed = time.time() - start_time
            logger.info(f"Issue fetch completed in {elapsed:.2f}s - Retrieved: {len(issues)} issues")

            logger.debug(f"Found {len(issues)} issues in current page (total: {total_count})")

            results = []
            # Track issue types for summary
            issue_type_counts = {}
            status_counts = {}
            priority_counts = {}

            for issue in issues:
                if not isinstance(issue, Issue):
                    logger.warning(f"Skipping non-Issue object: {issue}")
                    continue

                logger.debug(f"Processing issue {issue.key}")

                # Track for summary
                issue_type = issue.fields.issuetype.name if hasattr(issue.fields, "issuetype") else "Unknown"
                status = issue.fields.status.name
                priority = issue.fields.priority.name if issue.fields.priority else "Unknown"

                issue_type_counts[issue_type] = issue_type_counts.get(issue_type, 0) + 1
                status_counts[status] = status_counts.get(status, 0) + 1
                priority_counts[priority] = priority_counts.get(priority, 0) + 1

                # Always include key, summary, status
                issue_details = {
                    "key": issue.key,
                    "summary": issue.fields.summary,
                    "status": status,
                }

                # Add requested fields
                if "type" in requested_fields:
                    issue_details["type"] = issue_type

                if "assignee" in requested_fields:
                    issue_details["assignee"] = issue.fields.assignee.displayName if issue.fields.assignee else "Unassigned"

                if "priority" in requested_fields:
                    issue_details["priority"] = priority

                if "components" in requested_fields:
                    issue_details["components"] = [comp.name for comp in issue.fields.components] if issue.fields.components else []

                if "labels" in requested_fields:
                    issue_details["labels"] = list(issue.fields.labels) if issue.fields.labels else []

                # Timestamp fields
                if "created_date" in requested_fields:
                    issue_details["created_date"] = str(issue.fields.created) if issue.fields.created else None

                if "updated_date" in requested_fields:
                    issue_details["updated_date"] = str(issue.fields.updated) if issue.fields.updated else None

                # Custom fields
                if "target_version" in requested_fields:
                    try:
                        target_version_data = getattr(issue.fields, "customfield_12319940", None)
                        if target_version_data:
                            if isinstance(target_version_data, list):
                                issue_details["target_version"] = [v.name if hasattr(v, "name") else str(v) for v in target_version_data]
                            else:
                                issue_details["target_version"] = [
                                    target_version_data.name if hasattr(target_version_data, "name") else str(target_version_data)
                                ]
                    except (AttributeError, Exception) as e:
                        logger.debug(f"Could not extract target_version from {issue.key}: {e}")

                if "product_manager" in requested_fields:
                    try:
                        product_manager_data = getattr(issue.fields, "customfield_12316752", None)
                        if product_manager_data:
                            if hasattr(product_manager_data, "displayName"):
                                issue_details["product_manager"] = product_manager_data.displayName
                            elif isinstance(product_manager_data, str):
                                issue_details["product_manager"] = product_manager_data
                    except (AttributeError, Exception) as e:
                        logger.debug(f"Could not extract product_manager from {issue.key}: {e}")

                if "epic_link" in requested_fields:
                    epic_link = getattr(issue.fields, "customfield_12311140", None)
                    if epic_link:
                        issue_details["epic_link"] = epic_link

                if "pr_data" in requested_fields:
                    pr_data = getattr(issue.fields, "customfield_12310220", None)
                    if pr_data:
                        issue_details["pr_data"] = pr_data

                if "release_note_text" in requested_fields:
                    release_note_text = getattr(issue.fields, "customfield_12317313", None)
                    if release_note_text:
                        issue_details["release_note_text"] = release_note_text

                if "release_note_status" in requested_fields:
                    release_note_status = getattr(issue.fields, "customfield_12310213", None)
                    if release_note_status:
                        if hasattr(release_note_status, "get"):
                            status_value = release_note_status.get("value")
                        else:
                            status_value = str(release_note_status)
                        issue_details["release_note_status"] = status_value

                results.append(issue_details)

            logger.debug(f"Successfully processed {len(results)} issues for JQL '{jql_query}'")

            # Build response with summary
            response = {
                "query": jql_query,
                "issues": results,
            }

            if include_summary:
                response["summary"] = {
                    "total_count": total_count,
                    "returned_count": len(results),
                    "max_results": max_results,
                    "has_more": total_count > len(results),
                    "by_type": issue_type_counts,
                    "by_status": status_counts,
                    "by_priority": priority_counts,
                }

            return json.dumps(response, indent=2)

        except Exception as e:
            error_msg = f"Error searching issues with JQL '{jql_query}': {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})

    def add_comment(self, issue_key: str, comment: str) -> str:
        """Add a comment to a Jira issue.

        Args:
            issue_key: The key of the issue to comment on
            comment: The comment text to add

        Returns:
            JSON string indicating success or error
        """
        try:
            logger.debug(f"Adding comment to issue {issue_key}")
            logger.debug(f"Comment text length: {len(comment)} characters")

            jira = self._get_jira_client()
            result = jira.add_comment(issue_key, comment)

            logger.info(f"Comment added to issue {issue_key}")
            logger.debug(f"Comment result: {result}")

            return json.dumps(
                {
                    "status": "success",
                    "issue_key": issue_key,
                    "message": "Comment added successfully",
                }
            )

        except Exception as e:
            error_msg = f"Error adding comment to issue {issue_key}: {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})

    def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
        priority: str = "Medium",
        assignee: str | None = None,
        labels: list[str] | None = None,
    ) -> str:
        """Create a new Jira issue.

        Args:
            project_key: The key of the project to create the issue in
            summary: The summary/title of the issue
            description: The description of the issue
            issue_type: The type of issue (default: "Task")
            priority: The priority level (default: "Medium")
            assignee: Optional assignee username
            labels: Optional list of labels to add

        Returns:
            JSON string with the new issue's key and URL
        """
        try:
            logger.debug(f"Creating issue in project {project_key}")
            logger.debug(f"Issue type: {issue_type}, Priority: {priority}")
            logger.debug(f"Assignee: {assignee}, Labels: {labels}")
            logger.debug(f"Summary length: {len(summary)} characters")
            logger.debug(f"Description length: {len(description)} characters")

            jira = self._get_jira_client()

            # Build issue dictionary
            issue_dict = {
                "project": {"key": project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type},
                "priority": {"name": priority},
            }

            # Add assignee if provided
            if assignee:
                issue_dict["assignee"] = {"name": assignee}
                logger.debug(f"Added assignee: {assignee}")

            # Add labels if provided
            if labels:
                issue_dict["labels"] = labels
                logger.debug(f"Added labels: {labels}")

            logger.debug(f"Issue dictionary: {issue_dict}")

            new_issue = jira.create_issue(fields=issue_dict)
            issue_url = f"{self._server_url}/browse/{new_issue.key}"

            logger.info(f"Issue created with key: {new_issue.key}")
            logger.debug(f"Issue URL: {issue_url}")

            return json.dumps(
                {
                    "key": new_issue.key,
                    "url": issue_url,
                    "status": "success",
                    "message": f"Issue {new_issue.key} created successfully",
                }
            )

        except Exception as e:
            error_msg = f"Error creating issue in project {project_key}: {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})

    def extract_sprint_info(self, issue_key: str) -> str:
        """Extract sprint ID and name from an issue.

        Args:
            issue_key: The key of the issue to extract sprint info from

        Returns:
            JSON string with sprint info {"sprint_id": "123", "sprint_name": "Plugins Sprint 30482"}
            or None if unable to extract
        """
        try:
            logger.debug(f"Extracting sprint info from issue {issue_key}")
            jira = self._get_jira_client()

            issue = jira.issue(issue_key)
            sprint_data = getattr(issue.fields, "customfield_12310940", None)

            if not sprint_data:
                logger.warning(f"Issue {issue_key} has no sprint data (customfield_12310940)")
                return json.dumps(None)
            if not isinstance(sprint_data, list) or len(sprint_data) == 0:
                logger.warning(f"Issue {issue_key} has invalid sprint data format: {type(sprint_data)}")
                return json.dumps(None)
            last_sprint = str(sprint_data[-1])

            sprint_id = None
            id_match = re.search(r"id=(\d+)", last_sprint)
            if id_match:
                sprint_id = id_match.group(1)

            sprint_name = None
            name_match = re.search(r"name=([^,\]]+)", last_sprint)
            if name_match:
                sprint_name = name_match.group(1)
                logger.debug(f"Extracted sprint_name: {sprint_name}")

            if not sprint_id or not sprint_name:
                logger.warning(f"Could not extract complete sprint info from {issue_key}: id={sprint_id}, name={sprint_name}")
                return json.dumps(None)

            result = {
                "sprint_id": sprint_id,
                "sprint_name": sprint_name,
            }
            logger.info(f"Extracted sprint info from {issue_key}: {sprint_name} (ID: {sprint_id})")
            return json.dumps(result, indent=2)

        except Exception as e:
            error_msg = f"Error extracting sprint info from issue {issue_key}: {str(e)}"
            logger.error(error_msg)
            return json.dumps(None)

    def get_issues_by_team(
        self,
        release_version: str,
        team_ids: list[str],
        base_jql: str | None = None,
    ) -> str:
        """Get accurate issue counts by team for a release without pagination issues.

        This tool runs efficient count queries (maxResults=0) for each team to get
        accurate counts without fetching all issues. Solves the pagination problem
        where sampling first 50 issues gives incorrect team distributions.

        Args:
            release_version: Release version (e.g., "1.9.0")
            team_ids: List of team IDs to query (e.g., ["4267", "4564", "5775"])
            base_jql: Optional base JQL query to override default.
                      If None, uses default_base_jql from config.

        Returns:
            JSON string with team breakdown:
            {
                "release_version": "1.9.0",
                "total_issues": 587,
                "by_team": {
                    "4267": 100,
                    "4564": 98,
                    "5775": 63
                },
                "without_team": 326,
                "query_base": "project IN (...) AND fixVersion = \"1.9.0\""
            }

        Example:
            # Use default base query
            get_issues_by_team("1.9.0", ["4267", "4564"])

            # Override for code freeze
            get_issues_by_team(
                "1.9.0",
                ["4267", "4564"],
                base_jql="project IN (...) AND status NOT IN (closed, verified)"
            )
        """
        try:
            logger.debug(f"Getting issue counts by team for release {release_version}")
            logger.debug(f"Team IDs: {team_ids}")

            jira = self._get_jira_client()

            # Build base JQL query
            jql_parts = []

            # Use override if provided, else use default
            effective_base_jql = base_jql if base_jql is not None else self._default_base_jql
            if effective_base_jql:
                jql_parts.append(effective_base_jql)
                logger.debug(f"Using base JQL: {effective_base_jql}")

            jql_parts.append(f'fixVersion = "{release_version}"')
            base_jql_query = " AND ".join(jql_parts)

            # Get total count for the release
            logger.debug(f"Getting total count for release {release_version}")
            start_time = time.time()

            # CRITICAL: Use json_result=True to avoid fetching all issues!
            # When json_result=False (default), the library ignores maxResults=0 and fetches ALL issues
            logger.info(f"Querying Jira for total count: {base_jql_query[:100]}...")
            total_result = jira.search_issues(base_jql_query, maxResults=0, json_result=True)

            elapsed = time.time() - start_time
            total_count = total_result.get("total", 0)
            logger.info(f"Jira API call completed in {elapsed:.2f}s - Total count: {total_count}")

            # Get count for each team in PARALLEL for better performance
            team_counts = {}

            def query_team_count(team_id: str) -> tuple[str, int]:
                """Query count for a single team (used in parallel execution)."""
                try:
                    team_jql = f"{base_jql_query} AND team = {team_id}"

                    # Query Jira for team count (use json_result=True to avoid fetching all issues)
                    logger.info(f"Querying team {team_id}: {team_jql[:100]}...")
                    start_time = time.time()

                    team_result = jira.search_issues(team_jql, maxResults=0, json_result=True)

                    elapsed = time.time() - start_time
                    team_count = team_result.get("total", 0)
                    logger.info(f"Jira API call for team {team_id} completed in {elapsed:.2f}s - Count: {team_count}")
                    return team_id, team_count
                except Exception as e:
                    logger.error(f"Failed to query team {team_id}: {e}")
                    # Return 0 count on error instead of failing entire operation
                    return team_id, 0

            # Execute queries in parallel (max 10 concurrent to avoid overwhelming Jira)
            logger.info(f"Starting parallel queries for {len(team_ids)} teams (max 10 concurrent)")
            parallel_start = time.time()
            with ThreadPoolExecutor(max_workers=10) as executor:
                # Submit all team queries
                future_to_team = {executor.submit(query_team_count, tid): tid for tid in team_ids}

                # Collect results as they complete
                for future in as_completed(future_to_team):
                    team_id, count = future.result()
                    team_counts[team_id] = count
            parallel_elapsed = time.time() - parallel_start
            logger.info(f"Parallel queries completed in {parallel_elapsed:.2f}s for {len(team_ids)} teams")

            # Calculate issues without team assignment
            assigned_count = sum(team_counts.values())
            without_team = total_count - assigned_count

            result = {
                "release_version": release_version,
                "total_issues": total_count,
                "by_team": team_counts,
                "without_team": without_team,
                "query_base": base_jql_query,
            }

            logger.info(
                f"Team breakdown for {release_version}: {len(team_counts)} teams, {assigned_count} assigned, {without_team} unassigned"
            )

            return json.dumps(result, indent=2)

        except Exception as e:
            error_msg = f"Error getting issues by team for release {release_version}: {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})

    def get_sprint_metrics(self, sprint_id: str) -> str:
        """Calculate sprint metrics by running multiple JQL queries.

        This function performs multiple search queries to calculate:
        - Total planned tickets: Sprint = {sprint_id}
        - Total closed tickets: Sprint = {sprint_id} AND resolution = done
        - Closed stories/tasks: Sprint = {sprint_id} AND resolution = done AND type in (Story, Task)
        - Closed bugs: Sprint = {sprint_id} AND resolution = done AND type = Bug

        Args:
            sprint_id: The sprint ID to calculate metrics for (e.g., "75290")

        Returns:
            JSON string with metrics:
            {
                "sprint_id": "75290",
                "total_planned": 25,
                "total_closed": 18,
                "stories_tasks_closed": 15,
                "bugs_closed": 3
            }
        """
        try:
            logger.debug(f"Calculating sprint metrics for sprint_id={sprint_id}")
            jira = self._get_jira_client()

            jql_total_planned = f"Sprint = {sprint_id}"
            jql_total_closed = f"Sprint = {sprint_id} AND resolution = done"
            jql_stories_tasks_closed = f"Sprint = {sprint_id} AND resolution = done AND type in (Story, Task)"
            jql_bugs_closed = f"Sprint = {sprint_id} AND resolution = done AND type = Bug"

            logger.info(f"Fetching sprint metrics for sprint {sprint_id} (4 queries)")
            metrics_start = time.time()

            # Use json_result=True for all count queries (30x faster!)
            total_planned_results = jira.search_issues(jql_total_planned, maxResults=0, json_result=True)
            total_planned = total_planned_results.get("total", 0)

            total_closed_results = jira.search_issues(jql_total_closed, maxResults=0, json_result=True)
            total_closed = total_closed_results.get("total", 0)

            stories_tasks_results = jira.search_issues(jql_stories_tasks_closed, maxResults=0, json_result=True)
            stories_tasks_closed = stories_tasks_results.get("total", 0)

            bugs_results = jira.search_issues(jql_bugs_closed, maxResults=0, json_result=True)
            bugs_closed = bugs_results.get("total", 0)

            metrics_elapsed = time.time() - metrics_start
            logger.info(f"Sprint metrics queries completed in {metrics_elapsed:.2f}s")

            result = {
                "sprint_id": sprint_id,
                "total_planned": total_planned,
                "total_closed": total_closed,
                "stories_tasks_closed": stories_tasks_closed,
                "bugs_closed": bugs_closed,
            }
            return json.dumps(result, indent=2)

        except Exception as e:
            error_msg = f"Error calculating sprint metrics for sprint_id={sprint_id}: {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg})

    def update_issue(
        self,
        *,  # Force all parameters to be keyword-only
        issue_key: str,
        team_id: str | None = None,
        components: str | None = None,
        summary: str | None = None,
        description: str | None = None,
        assignee: str | None = None,
        labels: str | None = None,
    ) -> str:
        """Update an existing Jira issue.

        This tool allows updating various fields of a Jira issue including team assignment,
        components, summary, description, assignee, and labels.

        IMPORTANT: Only pass parameters for fields you want to UPDATE. Do NOT pass
        current values for fields you're not changing.

        NOTE: All parameters are keyword-only and must be passed by name.

        Args:
            issue_key: The Jira issue key (e.g., "RHIDP-6496") (keyword-only)
            team: (keyword-only) Team ID as a plain string (custom field customfield_12313240).
                  Use team ID from team_id_map. Example: "4267"
            components: (keyword-only) Comma-separated list of component names to set
            summary: (keyword-only) New summary/title for the issue (only pass if updating)
            description: (keyword-only) New description for the issue (only pass if updating)
            assignee: (keyword-only) Username or email of the assignee (only pass if updating)
            labels: (keyword-only) Comma-separated list of labels to set (only pass if updating)

        Returns:
            JSON string with update status and message
        """
        try:
            logger.info(f"Updating issue {issue_key}")
            jira = self._get_jira_client()

            # Build fields dictionary with only provided values
            fields = {}

            # Team field (custom field)
            if team_id is not None:
                fields["customfield_12313240"] = team_id
                logger.debug(f"Setting team to: {team_id}")

            # Components
            if components is not None:
                component_list = [c.strip() for c in components.split(",") if c.strip()]
                fields["components"] = [{"name": comp} for comp in component_list]
                logger.debug(f"Setting components to: {component_list}")

            # Summary
            if summary is not None:
                fields["summary"] = summary
                logger.debug(f"Setting summary to: {summary[:50]}...")

            # Description
            if description is not None:
                fields["description"] = description
                logger.debug(f"Setting description (length: {len(description)})")

            # Assignee
            if assignee is not None:
                # Try to set assignee, handle -1 for unassigned
                if assignee == "-1" or assignee.lower() == "unassigned":
                    fields["assignee"] = None
                    logger.debug("Unsetting assignee")
                else:
                    fields["assignee"] = {"name": assignee}
                    logger.debug(f"Setting assignee to: {assignee}")

            # Labels
            if labels is not None:
                label_list = [label.strip() for label in labels.split(",") if label.strip()]
                fields["labels"] = label_list
                logger.debug(f"Setting labels to: {label_list}")

            if not fields:
                return json.dumps({"status": "skipped", "message": "No fields provided to update"})

            logger.debug(f"Update fields: {fields}")

            # Perform the update
            issue = jira.issue(issue_key)
            issue.update(fields=fields)
            logger.debug(f"Updated issue {issue_key} with fields: {fields}")

            issue_url = f"{self._server_url}/browse/{issue_key}"
            logger.info(f"Successfully updated issue {issue_key}")

            return json.dumps(
                {
                    "key": issue_key,
                    "url": issue_url,
                    "status": "success",
                    "message": f"Issue {issue_key} updated successfully",
                    "updated_fields": list(fields.keys()),
                }
            )

        except Exception as e:
            error_msg = f"Error updating issue {issue_key}: {str(e)}"
            logger.error(error_msg)
            return json.dumps({"error": error_msg, "status": "failed"})
