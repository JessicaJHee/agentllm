"""Release Manager Configurator - Configuration management for Release Manager Agent."""

from typing import Any

from agno.db.sqlite import SqliteDb

from agentllm.agents.base import AgentConfigurator, BaseToolkitConfig
from agentllm.agents.toolkit_configs import GoogleDriveConfig
from agentllm.agents.toolkit_configs.jira_config import JiraConfig
from agentllm.agents.toolkit_configs.system_prompt_extension_config import (
    SystemPromptExtensionConfig,
)


class ReleaseManagerConfigurator(AgentConfigurator):
    """Configurator for Release Manager Agent.

    Handles configuration management and agent building for the Release Manager.
    """

    def __init__(
        self,
        user_id: str,
        session_id: str | None,
        shared_db: SqliteDb,
        token_storage,
        temperature: float | None = None,
        max_tokens: int | None = None,
        agent_kwargs: dict[str, Any] | None = None,
        system_prompt_local_file: str | None = None,
        **model_kwargs: Any,
    ):
        """Initialize Release Manager configurator.

        Args:
            user_id: User identifier
            session_id: Session identifier
            shared_db: Shared database
            token_storage: TokenStorage instance
            temperature: Optional model temperature
            max_tokens: Optional max tokens
            agent_kwargs: Additional Agent constructor kwargs
            system_prompt_local_file: Optional local file path for system prompt.
                                      If provided, reads from file instead of Google Drive.
                                      Useful for testing without OAuth.
            **model_kwargs: Additional model parameters
        """
        # Store token_storage for use in _initialize_toolkit_configs
        self._token_storage = token_storage
        # Store local file path for system prompt extension
        self._system_prompt_local_file = system_prompt_local_file

        # Call parent constructor (will call _initialize_toolkit_configs)
        super().__init__(
            user_id=user_id,
            session_id=session_id,
            shared_db=shared_db,
            temperature=temperature,
            max_tokens=max_tokens,
            agent_kwargs=agent_kwargs,
            **model_kwargs,
        )

    def _get_agent_name(self) -> str:
        """Get agent name for identification.

        Returns:
            str: Agent name
        """
        return "release-manager"

    def _get_agent_description(self) -> str:
        """Get agent description.

        Returns:
            str: Human-readable description
        """
        return "A helpful AI assistant"

    def _get_model_id(self) -> str:
        """Get model ID for Release Manager.

        For available Gemini models, see:
        https://ai.google.dev/gemini-api/docs/models/gemini

        Returns:
            str: Model ID (gemini-2.5-pro for Gemini 2.5)
        """
        return "gemini-2.5-pro"

    def _initialize_toolkit_configs(self) -> list[BaseToolkitConfig]:
        """Initialize toolkit configurations for Release Manager.

        Returns:
            list[BaseToolkitConfig]: List of toolkit configs
        """
        # ORDER MATTERS: SystemPromptExtensionConfig depends on GoogleDriveConfig
        gdrive_config = GoogleDriveConfig(token_storage=self._token_storage)

        # Configure Jira with Release Manager specific base JQL
        # The default_base_jql is applied to queries that need base scoping
        # (like get_issues_by_team) to scope to RHDH projects and filter by status
        jira_config = JiraConfig(
            token_storage=self._token_storage,
            default_base_jql="project IN (RHIDP, RHDHBugs, RHDHPLAN, RHDHSUPP) AND status != closed",
        )
        system_prompt_config = SystemPromptExtensionConfig(
            gdrive_config=gdrive_config,
            env_var_name="RELEASE_MANAGER_SYSTEM_PROMPT_GDRIVE_URL",
            local_file_path=self._system_prompt_local_file,
            token_storage=self._token_storage,
        )

        return [
            gdrive_config,
            jira_config,
            system_prompt_config,  # Must come after gdrive_config due to dependency
        ]

    def _build_agent_instructions(self) -> list[str]:
        """Build system prompt instructions for Release Manager.

        Returns:
            list[str]: List of instruction strings
        """
        return [
            "You are the Release Manager for Red Hat Developer Hub (RHDH).",
            "Your core responsibilities include:",
            "- Managing Y-stream releases (major versions like 1.7.0, 1.8.0)",
            "- Managing Z-stream releases (maintenance versions like 1.6.1, 1.6.2)",
            "- Tracking release progress, risks, and blockers",
            "- Coordinating with Engineering, QE, Documentation, and Product Management teams",
            "- Providing release status updates for meetings (SOS, Team Forum, Program Meeting)",
            "- Monitoring Jira for release-related issues, features, and bugs",
            "",
            "Available tools:",
            "- Jira: Query and analyze issues, epics, features, bugs, and CVEs",
            "- Google Drive: Access release schedules, test plans, documentation plans, and feature demos",
            "",
            "Jira Tool Usage - CRITICAL PAGINATION GUIDANCE:",
            "- Most Jira tools return SAMPLES of issues (default: 50, max: 1000 per query)",
            "- ALWAYS check 'summary.total_count' for accurate totals - it's ALWAYS correct",
            "- The 'summary.has_more' field indicates if there are more results beyond what was returned",
            "- Breakdown stats ('by_type', 'by_status', 'by_priority') are SAMPLE-BASED when has_more=true",
            "",
            "For Team Breakdowns (REQUIRED):",
            "- DO NOT count teams from get_issues_detailed() or get_issues_summary() results",
            "- ALWAYS use get_issues_by_team(release_version, team_ids) for accurate team counts",
            "- This tool runs efficient count-only queries per team (no pagination issues)",
            "- Workflow: 1) Get team IDs from Google Drive team mapping, 2) Call get_issues_by_team()",
            "",
            "When to increase max_results:",
            "- When displaying issue lists to users (e.g., 'show me blockers'), use max_results=100-1000",
            "- When you only need counts, use get_issues_stats() or get_issues_by_team() (no issue fetching)",
            "- When you need ALL issues and total > 1000, you'll need multiple queries with pagination",
            "",
            "Output guidelines:",
            "- Use markdown formatting for all structured output",
            "- Be concise but comprehensive in your responses",
            "- Provide data-driven insights with Jira query results and metrics",
            "- Include relevant links to Jira issues, and Google Docs resources",
            "- Use tables and bullet points for clarity",
            "",
            "Behavioral guidelines:",
            "- Proactively identify risks and blockers",
            "- Escalate critical issues with clear impact analysis",
            "- Base recommendations on concrete data (Jira metrics, test results, schedules)",
            "- Maintain professional communication appropriate for cross-functional stakeholders",
            "- Follow established release processes and policies",
            "",
            "System Prompt Management:",
            "- Your instructions come from TWO sources:",
            "  1. Embedded system prompt (stable, rarely changes): Core identity and capabilities",
            "  2. External system prompt (dynamic, frequently updated): Current release context, processes, examples",
            "- The external prompt is stored in a Google Drive document that users can directly edit",
            "- When release context seems outdated or incomplete, suggest users update the external prompt",
            "- If configured, you will be informed of the external prompt document URL in your extended instructions",
        ]

    def _build_model_params(self) -> dict[str, Any]:
        """Build model parameters with Gemini native thinking capability.

        Returns:
            dict: Model configuration parameters
        """
        params = super()._build_model_params()

        # Add Gemini native thinking parameters
        params["thinking_budget"] = 200  # Allocate up to 200 tokens for thinking
        params["include_thoughts"] = True  # Request thought summaries in response

        return params

    def _on_config_stored(self, config: BaseToolkitConfig) -> None:
        """Handle cross-config dependencies when configuration is stored.

        Special handling for GoogleDrive → SystemPromptExtension:
        When Google Drive credentials are updated, notify SystemPromptExtensionConfig
        to invalidate its cached system prompts.

        Args:
            config: The toolkit config that was stored
        """
        # When GoogleDrive credentials are updated, notify SystemPromptExtensionConfig
        if isinstance(config, GoogleDriveConfig):
            for other_config in self.toolkit_configs:
                if isinstance(other_config, SystemPromptExtensionConfig):
                    other_config.invalidate_for_gdrive_change(self.user_id)
                    break
