"""
GitHub Review Prioritization Agent - Intelligent PR review queue management.

This agent helps developers manage their PR review workload using multi-factor
prioritization algorithms to suggest which PRs to review next.
"""

import os

from agno.db.sqlite import SqliteDb

from agentllm.agents.base_agent import BaseAgentWrapper
from agentllm.agents.toolkit_configs.base import BaseToolkitConfig
from agentllm.agents.toolkit_configs.github_config import GitHubConfig
from agentllm.db import TokenStorage

# Map GEMINI_API_KEY to GOOGLE_API_KEY if not set
if "GOOGLE_API_KEY" not in os.environ and "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


class GitHubReviewAgent(BaseAgentWrapper):
    """GitHub PR Prioritization Agent.

    This agent specializes in helping developers manage their PR review queue
    by intelligently prioritizing pull requests based on multiple factors:
    - Age (older PRs get priority to avoid staleness)
    - Size (smaller PRs are easier to review)
    - Discussion activity (comments suggest urgency)
    - Labels (urgent/hotfix/blocking boost priority)
    - Author patterns (first-time contributors get attention)

    Key Features:
    - Multi-factor PR scoring algorithm (0-80 scale)
    - Priority tiers: CRITICAL, HIGH, MEDIUM, LOW
    - Review queue management
    - Repository velocity tracking
    - Smart review suggestions with reasoning

    Toolkit Configuration:
    - GitHub: Personal access token for repository access (optional)
    """

    def __init__(
        self,
        shared_db: SqliteDb,
        token_storage: TokenStorage,
        user_id: str,
        session_id: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **model_kwargs,
    ):
        """Initialize the GitHub Review Agent.

        Args:
            shared_db: Shared database instance for session management
            token_storage: Token storage instance for credentials
            user_id: User identifier (wrapper is per-user+session)
            session_id: Session identifier (optional)
            temperature: Model temperature (0.0-2.0)
            max_tokens: Maximum tokens in response
            **model_kwargs: Additional model parameters
        """
        # Store token_storage for toolkit config initialization
        self._token_storage = token_storage

        # Call parent constructor (will call _initialize_toolkit_configs)
        super().__init__(
            shared_db=shared_db,
            user_id=user_id,
            session_id=session_id,
            temperature=temperature,
            max_tokens=max_tokens,
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

    def _build_agent_instructions(self, user_id: str) -> list[str]:
        """Build agent-specific instructions for GitHub Review Agent.

        Args:
            user_id: User identifier

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

    def _build_model_params(self) -> dict:
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

    def _get_agent_kwargs(self) -> dict:
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
