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

        # Build tools list
        tools = [
            self.generate_color_palette,
            self.format_text_with_theme,
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
        """Generate complementary color palette."""
        logger.debug("_generate_complementary_palette() called")

        complement = self._complementary_colors.get(self.favorite_color, "gray")

        palette = (
            f"**Complementary Color Palette**\n\n"
            f"🎨 **Base Color:** {self.favorite_color.title()}\n"
            f"🎨 **Complementary:** {complement.title()}\n\n"
            f"This palette creates strong contrast and visual interest. "
            f"Complementary colors are opposite each other on the color wheel."
        )

        logger.debug(f"Generated palette with complement: {complement}")
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
