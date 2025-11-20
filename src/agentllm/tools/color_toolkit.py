"""
Color Tools - Simple utility tools for the Demo Agent.

This toolkit demonstrates simple tool creation without external API dependencies.
All tools use pure Python logic and extensive logging.
"""

from agno.tools import Toolkit
from loguru import logger


class ColorTools(Toolkit):
    """
    Simple color utility tools for demonstration purposes.

    These tools don't require external APIs and are designed to showcase:
    - Tool creation and registration
    - Using user configuration (favorite color)
    - Tool invocation logging
    - Simple, predictable outputs for testing
    """

    def __init__(self, favorite_color: str):
        """
        Initialize ColorTools with user's favorite color.

        Args:
            favorite_color: User's configured favorite color
        """
        logger.debug("=" * 80)
        logger.info(f"ColorTools.__init__() called with favorite_color={favorite_color}")

        self.favorite_color = favorite_color

        # Color theory mappings (simplified)
        self._complementary_colors = {
            "red": "green",
            "green": "red",
            "blue": "orange",
            "orange": "blue",
            "yellow": "purple",
            "purple": "yellow",
            "pink": "green",
            "black": "white",
            "white": "black",
            "brown": "blue",
        }

        self._analogous_colors = {
            "red": ["orange", "pink"],
            "orange": ["red", "yellow"],
            "yellow": ["orange", "green"],
            "green": ["yellow", "blue"],
            "blue": ["green", "purple"],
            "purple": ["blue", "pink"],
            "pink": ["purple", "red"],
            "black": ["brown", "purple"],
            "white": ["yellow", "pink"],
            "brown": ["orange", "red"],
        }

        # Hex code mappings for colors
        self._color_hex_codes = {
            "red": "#FF0000",
            "green": "#00FF00",
            "blue": "#0000FF",
            "orange": "#FFA500",
            "yellow": "#FFFF00",
            "purple": "#800080",
            "pink": "#FFC0CB",
            "black": "#000000",
            "white": "#FFFFFF",
            "brown": "#A52A2A",
            "gray": "#808080",
            "silver": "#C0C0C0",
            "darkseagreen4": "#698B69",
        }

        # Color mood mappings for intelligent scheme design
        self._color_moods = {
            "red": {"energy": 9, "warmth": 8, "calm": 2, "professional": 5, "creativity": 7},
            "blue": {"energy": 3, "warmth": 2, "calm": 9, "professional": 9, "creativity": 6},
            "green": {"energy": 5, "warmth": 4, "calm": 8, "professional": 7, "creativity": 5},
            "yellow": {"energy": 8, "warmth": 9, "calm": 3, "professional": 4, "creativity": 9},
            "purple": {"energy": 6, "warmth": 5, "calm": 6, "professional": 6, "creativity": 9},
            "orange": {"energy": 9, "warmth": 9, "calm": 2, "professional": 4, "creativity": 8},
            "pink": {"energy": 6, "warmth": 7, "calm": 5, "professional": 4, "creativity": 8},
            "black": {"energy": 4, "warmth": 1, "calm": 5, "professional": 10, "creativity": 5},
            "white": {"energy": 5, "warmth": 3, "calm": 7, "professional": 8, "creativity": 6},
            "brown": {"energy": 3, "warmth": 6, "calm": 6, "professional": 7, "creativity": 4},
        }

        # Build tools list
        tools = [
            self.generate_color_palette,
            self.format_text_with_theme,
            self.design_color_scheme_for_purpose,
        ]

        # Initialize parent Toolkit with tools
        super().__init__(name="color_tools", tools=tools)

        logger.info(f"✅ ColorTools initialized with {len(tools)} tools")
        logger.debug(f"Registered tools: {[t.__name__ for t in tools]}")
        logger.debug("=" * 80)

    def generate_color_palette(self, palette_type: str = "complementary") -> str:
        """
        Generate a color palette based on the user's favorite color.

        This tool demonstrates:
        - Simple tool with parameters
        - Using stored configuration (favorite_color)
        - Pure Python logic (no external APIs)
        - Structured output formatting

        Args:
            palette_type: Type of palette - "complementary", "analogous", or "monochromatic"

        Returns:
            Formatted color palette description
        """
        logger.debug("=" * 80)
        logger.info(">>> generate_color_palette() called")
        logger.info(f"Parameters: palette_type={palette_type}, favorite_color={self.favorite_color}")

        palette_type = palette_type.lower()

        # Validate palette type
        valid_types = ["complementary", "analogous", "monochromatic"]
        if palette_type not in valid_types:
            error_msg = f"Invalid palette_type '{palette_type}'. Must be one of: {', '.join(valid_types)}"
            logger.warning(error_msg)
            logger.info("<<< generate_color_palette() FINISHED (error)")
            logger.debug("=" * 80)
            return f"❌ Error: {error_msg}"

        logger.debug(f"✅ Palette type '{palette_type}' is valid")

        # Generate palette based on type
        try:
            if palette_type == "complementary":
                palette = self._generate_complementary_palette()
            elif palette_type == "analogous":
                palette = self._generate_analogous_palette()
            else:  # monochromatic
                palette = self._generate_monochromatic_palette()

            logger.info(f"✅ Generated {palette_type} palette: {palette}")
            logger.info("<<< generate_color_palette() FINISHED (success)")
            logger.debug("=" * 80)

            return palette

        except Exception as e:
            error_msg = f"Failed to generate palette: {str(e)}"
            logger.error(error_msg, exc_info=True)
            logger.info("<<< generate_color_palette() FINISHED (exception)")
            logger.debug("=" * 80)
            return f"❌ Error: {error_msg}"

    def _generate_complementary_palette(self) -> str:
        """Generate complementary color palette with hex codes."""
        logger.debug("_generate_complementary_palette() called")

        complement = self._complementary_colors.get(self.favorite_color, "gray")
        base_hex = self._color_hex_codes.get(self.favorite_color, "#808080")
        complement_hex = self._color_hex_codes.get(complement, "#808080")

        palette = (
            f"**Complementary Color Palette**\n\n"
            f"🎨 **Base Color:** {self.favorite_color.title()} (`{base_hex}`)\n"
            f"🎨 **Complementary:** {complement.title()} (`{complement_hex}`)\n\n"
            f"This palette creates strong contrast and visual interest. "
            f"Complementary colors are opposite each other on the color wheel."
        )

        logger.debug(f"Generated palette with complement: {complement} ({complement_hex})")
        return palette

    def _generate_analogous_palette(self) -> str:
        """Generate analogous color palette."""
        logger.debug("_generate_analogous_palette() called")

        analogous = self._analogous_colors.get(self.favorite_color, ["gray", "silver"])

        palette = (
            f"**Analogous Color Palette**\n\n"
            f"🎨 **Base Color:** {self.favorite_color.title()}\n"
            f"🎨 **Analogous 1:** {analogous[0].title()}\n"
            f"🎨 **Analogous 2:** {analogous[1].title()}\n\n"
            f"This palette creates harmony and calm. "
            f"Analogous colors are next to each other on the color wheel."
        )

        logger.debug(f"Generated palette with analogous colors: {analogous}")
        return palette

    def _generate_monochromatic_palette(self) -> str:
        """Generate monochromatic color palette."""
        logger.debug("_generate_monochromatic_palette() called")

        # For monochromatic, we describe variations of the same color
        palette = (
            f"**Monochromatic Color Palette**\n\n"
            f"🎨 **Base Color:** {self.favorite_color.title()}\n"
            f"🎨 **Light Variation:** Light {self.favorite_color.title()}\n"
            f"🎨 **Dark Variation:** Dark {self.favorite_color.title()}\n"
            f"🎨 **Muted Variation:** Muted {self.favorite_color.title()}\n\n"
            f"This palette creates a cohesive, sophisticated look using "
            f"different shades and tints of the same base color."
        )

        logger.debug("Generated monochromatic palette")
        return palette

    def format_text_with_theme(self, text: str, theme_style: str = "bold") -> str:
        """
        Format text with a color-themed description.

        This tool demonstrates:
        - Text processing
        - Using configuration in creative ways
        - Simple string manipulation

        Args:
            text: Text to format
            theme_style: Style to apply - "bold", "elegant", or "playful"

        Returns:
            Formatted text with color theme description
        """
        logger.debug("=" * 80)
        logger.info(">>> format_text_with_theme() called")
        logger.info(f"Parameters: text='{text[:50]}...', theme_style={theme_style}, favorite_color={self.favorite_color}")

        theme_style = theme_style.lower()

        # Validate theme style
        valid_styles = ["bold", "elegant", "playful"]
        if theme_style not in valid_styles:
            error_msg = f"Invalid theme_style '{theme_style}'. Must be one of: {', '.join(valid_styles)}"
            logger.warning(error_msg)
            logger.info("<<< format_text_with_theme() FINISHED (error)")
            logger.debug("=" * 80)
            return f"❌ Error: {error_msg}"

        logger.debug(f"✅ Theme style '{theme_style}' is valid")

        try:
            # Create themed description
            if theme_style == "bold":
                prefix = f"**[{self.favorite_color.upper()} THEMED]**"
                suffix = f"_(Presented in a bold {self.favorite_color} style)_"
            elif theme_style == "elegant":
                prefix = f"*~ {self.favorite_color.title()} Edition ~*"
                suffix = f"_(Elegantly styled with {self.favorite_color} accents)_"
            else:  # playful
                prefix = f"🎨✨ {self.favorite_color.title()} Fun! ✨🎨"
                suffix = f"_(Playfully themed in {self.favorite_color})_"

            formatted = f"{prefix}\n\n{text}\n\n{suffix}"

            logger.info(f"✅ Formatted text with {theme_style} theme")
            logger.debug(f"Result length: {len(formatted)} characters")
            logger.info("<<< format_text_with_theme() FINISHED (success)")
            logger.debug("=" * 80)

            return formatted

        except Exception as e:
            error_msg = f"Failed to format text: {str(e)}"
            logger.error(error_msg, exc_info=True)
            logger.info("<<< format_text_with_theme() FINISHED (exception)")
            logger.debug("=" * 80)
            return f"❌ Error: {error_msg}"

    def design_color_scheme_for_purpose(self, purpose: str) -> str:
        """
        Design a complete color scheme for a specific purpose or context.

        This tool demonstrates complex reasoning by:
        - Analyzing the purpose and extracting key requirements (mood, tone, context)
        - Evaluating multiple color options based on color psychology
        - Considering the user's favorite color preference
        - Making trade-offs between aesthetics, psychology, and purpose
        - Providing detailed reasoning for recommendations

        This tool is intentionally complex to trigger the agent's reasoning capabilities,
        showcasing step-by-step thinking and decision-making processes.

        Args:
            purpose: Description of the purpose or context (e.g., "calming meditation app",
                    "energetic sports brand", "professional corporate website",
                    "creative design portfolio", "welcoming restaurant")

        Returns:
            Detailed color scheme recommendation with reasoning
        """
        logger.debug("=" * 80)
        logger.info(">>> design_color_scheme_for_purpose() called")
        logger.info(f"Parameters: purpose='{purpose}', favorite_color={self.favorite_color}")

        try:
            # This tool is designed to be complex enough to trigger reasoning
            # The agent should think through:
            # 1. What mood/tone does this purpose require?
            # 2. Which colors match those requirements?
            # 3. How can we incorporate the user's favorite color?
            # 4. What are the trade-offs between different options?
            # 5. What is the optimal recommendation?

            # Extract keywords to determine mood requirements
            purpose_lower = purpose.lower()

            # Determine required mood characteristics
            requires_energy = any(
                word in purpose_lower for word in ["energy", "energetic", "active", "sport", "dynamic", "vibrant", "exciting"]
            )
            requires_calm = any(
                word in purpose_lower for word in ["calm", "calming", "meditation", "relax", "peaceful", "tranquil", "serene"]
            )
            requires_warmth = any(word in purpose_lower for word in ["warm", "welcoming", "friendly", "cozy", "inviting", "comfortable"])
            requires_professional = any(
                word in purpose_lower for word in ["professional", "corporate", "business", "formal", "executive", "official"]
            )
            requires_creativity = any(
                word in purpose_lower for word in ["creative", "artistic", "design", "innovative", "imaginative", "expressive"]
            )

            logger.debug(
                f"Mood analysis: energy={requires_energy}, calm={requires_calm}, warmth={requires_warmth}, professional={requires_professional}, creativity={requires_creativity}"
            )

            # Build mood profile
            mood_profile = {
                "energy": requires_energy,
                "warmth": requires_warmth,
                "calm": requires_calm,
                "professional": requires_professional,
                "creativity": requires_creativity,
            }

            # Evaluate how well the favorite color matches the requirements
            favorite_scores = self._color_moods.get(self.favorite_color, {})

            # Calculate overall match score for favorite color
            favorite_match_score = sum(
                score
                for mood, required in mood_profile.items()
                if required and mood in favorite_scores
                for score in [favorite_scores[mood]]
            )

            # Find best alternative colors for comparison
            best_alternatives = []
            for color, scores in self._color_moods.items():
                if color == self.favorite_color:
                    continue
                match_score = sum(
                    score for mood, required in mood_profile.items() if required and mood in scores for score in [scores[mood]]
                )
                best_alternatives.append((color, match_score))

            best_alternatives.sort(key=lambda x: x[1], reverse=True)
            top_alternative = best_alternatives[0] if best_alternatives else (None, 0)

            logger.debug(f"Favorite color match score: {favorite_match_score}")
            logger.debug(f"Top alternative: {top_alternative[0]} with score {top_alternative[1]}")

            # Build color scheme recommendation
            # Primary color: use favorite if it's a reasonable match, otherwise use best alternative
            use_favorite_as_primary = favorite_match_score >= (top_alternative[1] * 0.7)  # Within 70% of best

            if use_favorite_as_primary:
                primary_color = self.favorite_color
                primary_reasoning = f"Your favorite color ({self.favorite_color}) is a good match for this purpose."
            else:
                primary_color = top_alternative[0]
                primary_reasoning = (
                    f"While {self.favorite_color} is your favorite, {primary_color} better matches the '{purpose}' requirements."
                )

            # Supporting colors: build a harmonious palette
            if use_favorite_as_primary:
                # Use analogous colors of favorite
                supporting = self._analogous_colors.get(self.favorite_color, ["gray", "silver"])[:1]
                accent = self._complementary_colors.get(self.favorite_color, "gray")
            else:
                # Include favorite as accent to honor preference
                supporting = [self.favorite_color]
                accent = self._complementary_colors.get(primary_color, "gray")

            # Build detailed response
            response = f"""**Color Scheme Design for: "{purpose}"**

🎨 **Recommended Color Scheme:**

**Primary Color:** {primary_color.title()}
- Role: Main brand/theme color
- Reasoning: {primary_reasoning}

**Supporting Color(s):** {", ".join([c.title() for c in supporting])}
- Role: Secondary elements, backgrounds, UI components
- Reasoning: These colors harmonize with {primary_color} and provide visual variety

**Accent Color:** {accent.title()}
- Role: Call-to-action buttons, highlights, important elements
- Reasoning: Creates contrast and draws attention when needed

---

📊 **Analysis of Your Favorite Color ({self.favorite_color.title()}):**

"""

            # Add mood analysis for favorite color
            if self.favorite_color in self._color_moods:
                scores = self._color_moods[self.favorite_color]
                response += "Mood Characteristics (1-10 scale):\n"
                for mood, score in scores.items():
                    bar = "█" * score + "░" * (10 - score)
                    response += f"- {mood.title()}: {bar} ({score}/10)\n"

            # Add recommendation on usage
            response += "\n---\n\n💡 **Usage Recommendation:**\n\n"

            if use_favorite_as_primary:
                response += f"Great news! Your favorite color works well for this purpose. Use {primary_color} as the dominant color (60% of design), {supporting[0] if supporting else 'neutral tones'} for supporting elements (30%), and {accent} for accents (10%)."
            else:
                response += f"For optimal impact, use {primary_color} as the primary color, but incorporate {self.favorite_color} as a supporting or accent color to maintain your personal preference. This balances purpose-fit with personal taste."

            logger.info("✅ Successfully designed color scheme")
            logger.info("<<< design_color_scheme_for_purpose() FINISHED (success)")
            logger.debug("=" * 80)

            return response

        except Exception as e:
            error_msg = f"Failed to design color scheme: {str(e)}"
            logger.error(error_msg, exc_info=True)
            logger.info("<<< design_color_scheme_for_purpose() FINISHED (exception)")
            logger.debug("=" * 80)
            return f"❌ Error: {error_msg}"
