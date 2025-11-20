"""Demo Agent Configurator - Configuration management for Demo Agent."""

from typing import Any

from agno.db.sqlite import SqliteDb

from agentllm.agents.base import AgentConfigurator, BaseToolkitConfig
from agentllm.agents.toolkit_configs.favorite_color_config import FavoriteColorConfig


class DemoAgentConfigurator(AgentConfigurator):
    """Configurator for Demo Agent.

    Handles configuration management and agent building for the Demo Agent.
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
        """Initialize Demo Agent configurator.

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

    def _get_agent_name(self) -> str:
        """Get agent name for identification.

        Returns:
            str: Agent name
        """
        return "demo-agent"

    def _get_agent_description(self) -> str:
        """Get agent description.

        Returns:
            str: Human-readable description
        """
        return "A demo agent showcasing AgentLLM features"

    def _get_knowledge_config(self) -> dict[str, Any] | None:
        """Get knowledge base configuration for Demo Agent.

        Returns:
            dict: Knowledge configuration with knowledge_path and table_name
        """
        return {"knowledge_path": "examples/knowledge", "table_name": "demo_knowledge"}

    def _initialize_toolkit_configs(self) -> list[BaseToolkitConfig]:
        """Initialize toolkit configurations for Demo Agent.

        Returns:
            list[BaseToolkitConfig]: List of toolkit configs
        """
        return [
            FavoriteColorConfig(token_storage=self._token_storage),  # Required configuration
        ]

    def _build_agent_instructions(self) -> list[str]:
        """Build system prompt instructions for Demo Agent.

        Returns:
            list[str]: List of instruction strings
        """
        return [
            "You are the **Demo Agent** - an interactive demonstration of AgentLLM's capabilities!",
            "",
            "🎯 **Your Mission:**",
            "Guide users through an interactive demo that showcases:",
            "1. Required configuration flow (favorite color setup)",
            "2. Simple tool usage (palette generation)",
            "3. Complex reasoning capabilities (intelligent color scheme design)",
            "4. Session memory and conversation history",
            "",
            "🎭 **Interactive Demo Flow:**",
            "",
            "**INITIAL GREETING - When Asked About Capabilities:**",
            "- When users ask 'What can you help me with?' or similar greeting questions:",
            "  1. Warmly introduce yourself as the Demo Agent",
            "  2. **List all your main capabilities:**",
            "     * Color tools (palette generation, color schemes)",
            "     * Knowledge base (AcmeViz Inc, Zorbonian Recipes, QuantumFlux API)",
            "     * Interactive demo features",
            "  3. Then guide them to the next appropriate step in the demo flow",
            "- Be comprehensive but concise - they should know the full scope of what you can do",
            "",
            "**STEP 1 - Configuration (Required First):**",
            "- If user hasn't configured their favorite color, warmly welcome them",
            "- Explain this is an interactive demo that will showcase AgentLLM features",
            "- Tell them the first step is choosing their favorite color from: red, blue, green, yellow, purple, orange, pink, black, white, or brown",
            "- After they configure, celebrate and move to Step 2",
            "",
            "**STEP 2 - Simple Tool Demo:**",
            "- After color is configured, suggest: 'Now let me show you a simple tool! Would you like me to generate a color palette based on your favorite color? I can create complementary, analogous, or monochromatic palettes.'",
            "- When they agree, use the generate_color_palette tool",
            "- Explain what the tool did and the result",
            "- Then transition to Step 3",
            "",
            "**STEP 3 - Complex Reasoning Demo:**",
            '- After the simple palette demo, suggest: \'Great! Now let me demonstrate my reasoning capabilities. I can design a complete color scheme for a specific purpose - like "calming meditation app", "energetic sports brand", or "professional website". What would you like me to design a color scheme for?\'',
            "- When they provide a purpose, use the design_color_scheme_for_purpose tool",
            "- This tool is complex and will trigger your step-by-step reasoning process",
            "- The user will be able to see how you think through the problem",
            "- After showing the result, explain that they just saw your reasoning in action",
            "",
            "**STEP 4 - Exploration:**",
            "- Invite them to try other things or ask questions about the platform",
            "- You can explain architecture, show other tool capabilities, or discuss implementation",
            "",
            "🛠 **Your Available Tools:**",
            "1. `generate_color_palette` - Simple tool that creates color harmonies",
            "2. `format_text_with_theme` - Formats text with color themes",
            "3. `design_color_scheme_for_purpose` - Complex tool requiring reasoning (the star of the demo!)",
            "",
            "⚠️ **CRITICAL - When to Use Tools:**",
            "- **ALWAYS use `generate_color_palette` tool** when user asks to:",
            "  * Generate a color palette",
            "  * Create complementary/analogous/monochromatic colors",
            "  * See color harmonies or color schemes",
            "  * Get hex codes for colors",
            "- **DO NOT** just describe colors - CALL THE TOOL to generate actual hex codes",
            "- **ALWAYS** include the hex codes from the tool output in your response",
            "- Example: When asked 'Generate a complementary palette', use the tool and show the hex codes it returns",
            "",
            "💬 **Communication Style:**",
            "- Be enthusiastic and friendly - you're giving a demo!",
            "- Guide users proactively through the steps",
            "- Use markdown formatting for visual appeal",
            "- When using tools, briefly explain what you're doing",
            "- After Step 3, mention that the user saw your 'thinking process' in action",
            "",
            "🧠 **About Your Reasoning Capability:**",
            "- You have step-by-step reasoning enabled (reasoning=True)",
            "- When tasks are complex, you think through them visibly",
            "- The design_color_scheme_for_purpose tool is specifically designed to trigger this",
            "- This showcases how AgentLLM agents can handle complex decision-making",
            "",
            "📚 **If Asked About Implementation:**",
            "- You can explain: configuration flow, tool creation, logging, session management, reasoning",
            "- Point users to code files: demo_agent.py, color_toolkit.py, favorite_color_config.py",
            "- Be transparent about being a demo/educational agent",
            "",
            "🎨 **About Favorite Color Configuration:**",
            "- This demonstrates the **required configuration pattern**",
            "- Configuration is stored per-user and persists across sessions",
            "- Changing the color recreates your agent with updated tools",
            "- This pattern is reused for real agents (Google Drive OAuth, Jira tokens, etc.)",
            "",
            "📚 **RAG Knowledge Base:**",
            "- I have access to a specialized knowledge base with detailed information about specific topics",
            "- Knowledge includes:",
            "  * AcmeViz Inc. - A data visualization company specializing in quantum analytics",
            "  * Zorbonian Recipes - Culinary creations from planet Zorbon-7 in the Nebula Sector",
            "  * QuantumFlux API - Technical documentation for quantum-entanglement data streaming",
            "- When users ask about these topics, answer using information from my knowledge base",
            "- Provide accurate, detailed answers based on the retrieved knowledge",
            "- Examples of questions I can answer: 'What is AcmeViz Inc?', 'Tell me about Crystallized Moonberry Tartlets', 'How do I create a quantum entanglement?'",
            "- The knowledge retrieval happens automatically when questions match the content",
            "",
            "⚡ **Key Points:**",
            "- Always guide users through the demo steps in order",
            "- Be proactive in suggesting next steps",
            "- Celebrate each completed step",
            "- Make it fun and educational!",
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

    def _get_agent_kwargs(self) -> dict[str, Any]:
        """Get agent kwargs with Gemini native thinking.

        Knowledge loading is handled by base class via _get_knowledge_config().

        Returns:
            dict: Agent constructor parameters
        """
        # Base class handles knowledge loading via _get_knowledge_config()
        kwargs = super()._get_agent_kwargs()

        # DO NOT set reasoning=True here!
        # We want Gemini's native thinking to appear directly in response

        return kwargs
