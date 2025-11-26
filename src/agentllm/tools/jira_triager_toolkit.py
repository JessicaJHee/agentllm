"""
Jira Triager toolkit for logic-based team and component recommendations.

This toolkit provides tools for triaging Jira tickets using component mappings,
keyword analysis, and assignee validation. The agent instructions define the
decision algorithm and team-specific keyword patterns.
"""

import json

from agno.tools import Toolkit
from loguru import logger
from pydantic import BaseModel, Field

try:
    from jira import JIRA
except ImportError:
    raise ImportError("`jira` not installed. Please install using `pip install jira`") from None


class JiraTriageRecommendation(BaseModel):
    """Pydantic model for triage recommendation."""

    team: str | None = Field(None, description="Recommended team assignment")
    components: list[str] | None = Field(None, description="Recommended component assignments")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0")
    reasoning: str | None = Field(None, description="Explanation for the recommendation")


class JiraTriagerTools(Toolkit):
    """Toolkit for triaging Jira tickets using logic-based analysis."""

    def __init__(
        self,
        jira_token: str,
        jira_url: str,
    ):
        """
        Initialize the Jira Triager toolkit.

        Args:
            jira_token: Jira API token for authentication
            jira_url: Jira server URL
        """
        super().__init__(name="jira_triager_tools")

        self.jira_token = jira_token
        self.jira_url = jira_url

        # Jira client (lazy loaded)
        self._jira_client: JIRA | None = None

        logger.debug("JiraTriagerTools initialized for logic-based triage")

        # Register tools
        self.register(self.triage_ticket)

    def _get_jira_client(self) -> JIRA:
        """Get or create the Jira client."""
        if self._jira_client is None:
            logger.debug(f"Connecting to Jira at {self.jira_url}")
            self._jira_client = JIRA(server=self.jira_url, token_auth=self.jira_token)
        return self._jira_client

    def _clean_jira_description(self, text: str | None) -> str:
        """Clean Jira description text."""
        if not text:
            return ""
        cleaned = text.replace("{noformat}", "")
        cleaned = cleaned.replace("\r\n", "\n").replace("\r", "")
        return cleaned.strip()

    def _get_project_components(self, project_key: str) -> list[str]:
        """Get list of allowed component names for a Jira project.

        Args:
            project_key: Jira project key (e.g., "RHIDP")

        Returns:
            List of component names allowed in the project
        """
        try:
            jira = self._get_jira_client()
            project = jira.project(project_key)
            components = jira.project_components(project)
            component_names = [comp.name for comp in components]
            logger.debug(f"Found {len(component_names)} components for project {project_key}")
            return component_names
        except Exception as e:
            logger.warning(f"Failed to fetch components for project {project_key}: {e}")
            return []

    def triage_ticket(
        self,
        issue_key: str,
        override_title: str | None = None,
        override_description: str | None = None,
        override_team: str | None = None,
        override_components: str | None = None,
    ) -> str:
        """
        Recommend team and component assignments for a Jira ticket using logic-based analysis.

        This tool analyzes the ticket content using component mappings, keyword patterns,
        and assignee validation as defined in the agent instructions. The agent performs
        the actual decision logic based on COMPONENT_TEAM_MAP, keyword analysis, and
        TEAM_ASSIGNEE_MAP.

        Args:
            issue_key: Jira ticket ID (e.g., "RHIDP-6496")
            override_title: Override the fetched title (optional)
            override_description: Override the fetched description (optional)
            override_team: Override the fetched team (optional)
            override_components: Override the fetched components as comma-separated list (optional)

        Returns:
            JSON string with ticket data for agent analysis: {
                "issue_key": "RHIDP-6496",
                "current_team": "...",
                "current_components": [...],
                "current_assignee": "...",
                "title": "...",
                "description": "..."
            }
        """
        try:
            # Fetch ticket details from Jira
            jira = self._get_jira_client()
            issue = jira.issue(issue_key, expand="renderedFields")
            fields = issue.fields

            # Get project key and allowed components
            project_key = getattr(fields, "project", None)
            if project_key:
                project_key = project_key.key if hasattr(project_key, "key") else str(project_key)
            else:
                project_key = "RHIDP"  # Default fallback

            allowed_components = self._get_project_components(project_key)

            # Extract current ticket data
            title = override_title if override_title else getattr(fields, "summary", "")
            description = override_description if override_description else self._clean_jira_description(getattr(fields, "description", ""))

            # Extract current components
            current_components: list[str] = []
            if override_components is not None:
                current_components = [c.strip() for c in override_components.split(",") if c.strip()]
            else:
                components_objs = getattr(fields, "components", [])
                current_components = [comp.name for comp in components_objs] if components_objs else []

            # Extract current team
            current_team = override_team if override_team is not None else None
            if current_team is None:
                team_field = getattr(fields, "customfield_12313240", None)
                if team_field is not None and hasattr(team_field, "name"):
                    current_team = team_field.name
                elif isinstance(team_field, dict) and "name" in team_field:
                    current_team = team_field["name"]
                elif isinstance(team_field, str):
                    current_team = team_field

            # Extract current assignee (for TEAM_ASSIGNEE_MAP validation)
            current_assignee = None
            assignee_field = getattr(fields, "assignee", None)
            if assignee_field is not None:
                if hasattr(assignee_field, "displayName"):
                    current_assignee = assignee_field.displayName
                elif isinstance(assignee_field, dict) and "displayName" in assignee_field:
                    current_assignee = assignee_field["displayName"]
                elif hasattr(assignee_field, "name"):
                    current_assignee = assignee_field.name
                elif isinstance(assignee_field, dict) and "name" in assignee_field:
                    current_assignee = assignee_field["name"]

            # Determine missing fields
            missing_fields = []
            if not current_team:
                missing_fields.append("team")
            if not current_components:
                missing_fields.append("components")

            if not missing_fields:
                return json.dumps(
                    {
                        "message": f"Ticket {issue_key} already has both team and components assigned",
                        "team": current_team,
                        "components": current_components,
                    }
                )

            # Return ticket data for agent to analyze using logic-based rules
            ticket_data = {
                "issue_key": issue_key,
                "project_key": project_key,
                "title": title,
                "description": description,
                "current_team": current_team,
                "current_components": current_components,
                "current_assignee": current_assignee,
                "missing_fields": missing_fields,
                "allowed_components": allowed_components,
            }

            return json.dumps(ticket_data, indent=2)

        except Exception as e:
            logger.error(f"Failed to triage ticket {issue_key}: {e}")
            return json.dumps({"error": str(e)}, indent=2)
