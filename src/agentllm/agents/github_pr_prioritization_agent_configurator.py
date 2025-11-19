"""GitHub PR Prioritization Agent Configurator - Configuration management for GitHub Review Agent."""

from typing import Any

from agno.db.sqlite import SqliteDb

from agentllm.agents.base import AgentConfigurator, BaseToolkitConfig
from agentllm.agents.toolkit_configs.github_config import GitHubConfig


class GitHubReviewAgentConfigurator(AgentConfigurator):
    """Configurator for GitHub PR Prioritization Agent.

    Handles configuration management and agent building for the GitHub Review Agent.
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
        **model_kwargs: Any,
    ):
        """Initialize GitHub Review Agent configurator.

        Args:
            user_id: User identifier
            session_id: Session identifier
            shared_db: Shared database
            token_storage: TokenStorage instance
            temperature: Optional model temperature
            max_tokens: Optional max tokens
            agent_kwargs: Additional Agent constructor kwargs
            **model_kwargs: Additional model parameters
        """
        # Store token_storage for use in _initialize_toolkit_configs
        self._token_storage = token_storage

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

    def _initialize_toolkit_configs(self) -> list[BaseToolkitConfig]:
        """Initialize toolkit configurations for GitHub Review Agent.

        Returns:
            List of toolkit configuration instances
        """
        return [
            GitHubConfig(token_storage=self._token_storage),  # Optional: prompts when GitHub mentioned
        ]

    def _get_agent_name(self) -> str:
        """Return agent name."""
        return "github-pr-prioritization"

    def _get_agent_description(self) -> str:
        """Return agent description."""
        return "GitHub PR Prioritization - Multi-factor scoring and intelligent queue management"

    def _build_agent_instructions(self) -> list[str]:
        """Build agent-specific instructions for GitHub Review Agent.

        Returns:
            List of instruction strings
        """
        return [
            "You are a GitHub PR review assistant that helps developers manage their review queue efficiently.",
            "",
            "## Your Role",
            "Help users prioritize pull requests and decide what to review next. The scoring and prioritization algorithms are handled by your tools - you focus on interpreting results and making recommendations.",
            "",
            "## How to Help Users",
            "",
            "### For General Queue Requests:",
            "1. Use `prioritize_prs` to get scored PRs",
            "2. Present results clearly with context about priority tiers",
            "3. Highlight critical/urgent items (CRITICAL tier: 65-80 score)",
            "",
            "### For Next Review Recommendations:",
            "1. Use `suggest_next_review` for intelligent recommendations",
            "2. Explain the reasoning provided by the tool",
            "3. Offer alternatives if the top recommendation isn't suitable",
            "",
            "### For Repository Health:",
            "1. Use `get_repo_velocity` to show merge metrics",
            "2. Interpret trends (avg time to merge, PRs per day)",
            "3. Identify potential bottlenecks",
            "",
            "## Output Guidelines",
            "- Use emojis for priority: 🔴 Critical (65-80), 🟡 High/Medium (35-64), 🟢 Low (0-34)",
            "- Show score breakdowns when helpful (the tools provide them)",
            "- Be conversational and actionable",
            "- Explain WHY a PR is prioritized, not just the score",
            "",
            "## Example Interactions",
            "",
            '**User**: "Show me the review queue for facebook/react"',
            "**You**: Use `prioritize_prs('facebook/react', 10)` and present top PRs with their scores and tiers",
            "",
            '**User**: "What should I review next?"',
            "**You**: Use `suggest_next_review(repo, username)` and explain the recommendation",
            "",
            '**User**: "How\'s the team doing on reviews?"',
            "**You**: Use `get_repo_velocity(repo, 7)` and interpret the metrics",
        ]

    def _build_model_params(self) -> dict[str, Any]:
        """Override to configure Gemini with native thinking capability.

        Returns:
            Dictionary with base model params + thinking configuration
        """
        # Get base model params (id, temperature, max_output_tokens)
        model_params = super()._build_model_params()

        # Add Gemini native thinking parameters
        model_params["thinking_budget"] = 200  # Allocate tokens for thinking
        model_params["include_thoughts"] = True  # Request thought summaries

        return model_params

    def _get_agent_kwargs(self) -> dict[str, Any]:
        """Get agent kwargs without Agno's reasoning agent.

        We rely on Gemini's native thinking instead of Agno's ReasoningAgent.

        Returns:
            Dictionary with base defaults (NO reasoning=True)
        """
        # Get base defaults (db, add_history_to_context, etc.)
        kwargs = super()._get_agent_kwargs()

        # DO NOT set reasoning=True - we use Gemini's native thinking
        # Gemini will include thinking directly in response as <details> blocks

        return kwargs
