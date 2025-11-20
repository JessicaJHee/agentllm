"""Consolidated accuracy evaluation tests for demo agent.

Tests core functionality: basic agent behavior, tool usage, and RAG knowledge retrieval.
"""

import pytest
from agno.eval.accuracy import AccuracyEval, AccuracyResult
from agno.models.google import Gemini


@pytest.mark.eval
def test_basic_greeting(configured_demo_configurator):
    """Test basic greeting conversation accuracy.

    Verifies that the agent responds appropriately to greetings and mentions
    its capabilities.
    """
    # Build agent
    agent = configured_demo_configurator.build_agent()

    # Create evaluation
    evaluation = AccuracyEval(
        name="Basic Greeting",
        model=Gemini(id="gemini-2.0-flash-exp"),
        agent=agent,
        input="Hello! What can you help me with?",
        expected_output=(
            "Should mention being a demo agent, color tools (palette generation), "
            "and knowledge base about AcmeViz, Zorbonian recipes, and QuantumFlux API"
        ),
        additional_guidelines=("Agent should be friendly and welcoming. Response should clearly list main capabilities."),
        num_iterations=2,
    )

    # Run evaluation
    result: AccuracyResult | None = evaluation.run(print_results=True)

    # Assert accuracy
    assert result is not None, "Evaluation should return a result"
    assert result.avg_score >= 7.0, f"Expected score >= 7.0, got {result.avg_score}"


@pytest.mark.eval
def test_configuration_prompt(demo_configurator):
    """Test that agent prompts for configuration when not configured.

    Verifies that the agent correctly asks for favorite color when it's not set.
    """
    # Build agent WITHOUT configuring favorite color
    agent = demo_configurator.build_agent()

    # Create evaluation
    evaluation = AccuracyEval(
        name="Configuration Prompt",
        model=Gemini(id="gemini-2.0-flash-exp"),
        agent=agent,
        input="Hello!",
        expected_output=(
            "Should ask the user to choose their favorite color from the list: "
            "red, blue, green, yellow, purple, orange, pink, black, white, brown. "
            "Should explain this is part of the demo setup."
        ),
        additional_guidelines=(
            "Agent must prompt for color configuration. "
            "Must list the available color choices. "
            "Should be friendly and explain why configuration is needed."
        ),
        num_iterations=1,  # Only need one iteration since this is deterministic
    )

    # Run evaluation
    result: AccuracyResult | None = evaluation.run(print_results=True)

    # Assert accuracy
    assert result is not None
    assert result.avg_score >= 7.0, f"Expected score >= 7.0, got {result.avg_score}"


@pytest.mark.eval
def test_color_palette_tool(configured_demo_configurator):
    """Test color palette generation tool usage accuracy.

    Verifies that the agent correctly uses the color palette generation tool.
    """
    # Build agent
    agent = configured_demo_configurator.build_agent()

    # Create evaluation
    evaluation = AccuracyEval(
        name="Color Palette Generation",
        model=Gemini(id="gemini-2.0-flash-exp"),
        agent=agent,
        input="Generate a complementary color palette based on my favorite color",
        expected_output=(
            "Should use the generate_color_palette tool and provide a list of "
            "complementary colors in hex format. Should explain that complementary "
            "colors are opposite on the color wheel."
        ),
        additional_guidelines=(
            "Agent must use the generate_color_palette tool. "
            "Response should include hex color codes (e.g., #RRGGBB format). "
            "Must specify palette type as 'complementary'."
        ),
        num_iterations=2,
    )

    # Run evaluation
    result: AccuracyResult | None = evaluation.run(print_results=True)

    # Assert accuracy
    assert result is not None
    assert result.avg_score >= 7.0, f"Expected score >= 7.0, got {result.avg_score}"


@pytest.mark.eval
@pytest.mark.integration
def test_rag_acmeviz(configured_demo_configurator):
    """Test RAG retrieval accuracy for AcmeViz knowledge.

    Verifies that the agent correctly retrieves the CEO name from the knowledge base.
    """
    # Build agent
    agent = configured_demo_configurator.build_agent()

    # Create evaluation
    evaluation = AccuracyEval(
        name="RAG - AcmeViz CEO",
        model=Gemini(id="gemini-2.0-flash-exp"),
        agent=agent,
        input="Who is the CEO of AcmeViz Inc?",
        expected_output="Dr. Zenith Brighthouse",
        additional_guidelines=("Must retrieve the exact CEO name from the knowledge base. The answer should be definitive and accurate."),
        num_iterations=2,
    )

    # Run evaluation
    result: AccuracyResult | None = evaluation.run(print_results=True)

    # Assert accuracy
    assert result is not None, "Evaluation should return a result"
    assert result.avg_score >= 8.0, f"Expected score >= 8.0, got {result.avg_score}"


@pytest.mark.eval
@pytest.mark.integration
def test_rag_zorbonian(configured_demo_configurator):
    """Test RAG retrieval for Zorbonian recipe knowledge.

    Verifies that the agent correctly retrieves fictional recipe ingredients.
    """
    # Build agent
    agent = configured_demo_configurator.build_agent()

    # Create evaluation
    evaluation = AccuracyEval(
        name="RAG - Zorbonian Recipe",
        model=Gemini(id="gemini-2.0-flash-exp"),
        agent=agent,
        input="What are the main ingredients for Crystallized Moonberry Tartlets?",
        expected_output=(
            "Main ingredients include: Crystallized Moonberries, Zorbonian Cloudwheat Flour, "
            "Quantum-Churned Nebula Butter, Stardust Sugar, Harvested Sunbeam Essence, "
            "and Quantum Water. For the filling: Crystallized Moonberries, Stardust Sugar, "
            "Lunar Citrus Juice, Quantum Cornstarch, and Nebula Essence Extract."
        ),
        additional_guidelines=(
            "Must mention the fictional ingredients from the Zorbonian recipe. "
            "Should include both pastry shell and filling ingredients. "
            "Key ingredients: Crystallized Moonberries, Cloudwheat Flour, Nebula Butter, Stardust Sugar."
        ),
        num_iterations=2,
    )

    # Run evaluation
    result: AccuracyResult | None = evaluation.run(print_results=True)

    # Assert accuracy
    assert result is not None
    assert result.avg_score >= 7.0, f"Expected score >= 7.0, got {result.avg_score}"


@pytest.mark.eval
@pytest.mark.integration
def test_rag_quantumflux(configured_demo_configurator):
    """Test RAG retrieval for QuantumFlux API knowledge.

    Verifies that the agent retrieves the correct API base URL.
    """
    # Build agent
    agent = configured_demo_configurator.build_agent()

    # Create evaluation
    evaluation = AccuracyEval(
        name="RAG - QuantumFlux API",
        model=Gemini(id="gemini-2.0-flash-exp"),
        agent=agent,
        input="What is the base URL for the QuantumFlux API?",
        expected_output="https://api.quantumflux.example/v3",
        additional_guidelines=("Must retrieve the exact base URL from the API documentation. URL must be complete and accurate."),
        num_iterations=2,
    )

    # Run evaluation
    result: AccuracyResult | None = evaluation.run(print_results=True)

    # Assert accuracy
    assert result is not None
    assert result.avg_score >= 8.5, f"Expected score >= 8.5, got {result.avg_score}"


@pytest.mark.eval
@pytest.mark.integration
def test_unknown_topic(configured_demo_configurator):
    """Test agent response to unknown topics (not in knowledge base).

    Verifies that the agent appropriately indicates when information
    is not in its knowledge base and doesn't hallucinate.
    """
    # Build agent
    agent = configured_demo_configurator.build_agent()

    # Create evaluation
    evaluation = AccuracyEval(
        name="Unknown Topic Handling",
        model=Gemini(id="gemini-2.0-flash-exp"),
        agent=agent,
        input="What is the population of Tokyo in 2024?",
        expected_output=(
            "Agent should indicate this information is not in its knowledge base. "
            "May provide general information if available from training data, "
            "but should not claim to have specific knowledge about this."
        ),
        additional_guidelines=(
            "Agent should NOT fabricate information. "
            "Should be honest about knowledge limitations. "
            "May mention that its knowledge base contains AcmeViz, Zorbonian recipes, and QuantumFlux API docs."
        ),
        num_iterations=1,
    )

    # Run evaluation
    result: AccuracyResult | None = evaluation.run(print_results=True)

    # Assert accuracy
    assert result is not None
    assert result.avg_score >= 7.0, f"Expected score >= 7.0, got {result.avg_score}"


@pytest.mark.eval
def test_mixed_capabilities(configured_demo_configurator):
    """Test agent handles mixed requests (tools + knowledge).

    Verifies the agent can handle questions that involve both
    its tools and knowledge base.
    """
    # Build agent
    agent = configured_demo_configurator.build_agent()

    # Create evaluation
    evaluation = AccuracyEval(
        name="Mixed Capabilities",
        model=Gemini(id="gemini-2.0-flash-exp"),
        agent=agent,
        input="Can you help me with color schemes and also tell me about companies that make visualization software?",
        expected_output=(
            "Should mention ability to generate color palettes using tools, "
            "and should reference AcmeViz Inc from the knowledge base as an example "
            "of a company that makes visualization software."
        ),
        additional_guidelines=(
            "Agent should demonstrate both tool usage (color capabilities) "
            "and knowledge retrieval (AcmeViz). "
            "Response should be coherent and address both parts of the question."
        ),
        num_iterations=2,
    )

    # Run evaluation
    result: AccuracyResult | None = evaluation.run(print_results=True)

    # Assert accuracy
    assert result is not None
    assert result.avg_score >= 6.5, f"Expected score >= 6.5, got {result.avg_score}"
