"""Release Manager agent for managing software releases and changelogs."""

from pathlib import Path
from typing import Optional

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.google import Gemini

# Shared database for all agents to enable session management
DB_PATH = Path("tmp/agno_sessions.db")
DB_PATH.parent.mkdir(exist_ok=True)
shared_db = SqliteDb(db_file=str(DB_PATH))


def create_release_manager(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **model_kwargs,
) -> Agent:
    """Create a release manager agent that helps with software releases.

    Args:
        temperature: Model temperature (0.0-2.0)
        max_tokens: Maximum tokens in response
        **model_kwargs: Additional model parameters

    Returns:
        Agent instance configured for release management tasks
    """
    model_params = {"id": "gemini-2.5-flash"}
    if temperature is not None:
        model_params["temperature"] = temperature
    if max_tokens is not None:
        model_params["max_tokens"] = max_tokens
    model_params.update(model_kwargs)

    return Agent(
        name="release-manager",
        model=Gemini(**model_params),
        description=(
            "A release management assistant that helps with software "
            "releases, changelogs, and version planning"
        ),
        instructions=[
            "You are an expert release manager and software engineering " "assistant.",
            "Help users plan releases, create changelogs, manage versions, "
            "and coordinate deployment activities.",
            "Provide guidance on semantic versioning, release notes, and "
            "best practices.",
            "Be thorough in analyzing changes and their impact on users.",
            "Use markdown formatting for structured output.",
        ],
        markdown=True,
        # Session management
        db=shared_db,
        add_history_to_context=True,
        num_history_runs=10,  # Include last 10 messages
        read_chat_history=True,  # Allow agent to read full history
    )


def get_agent(
    agent_name: str = "release-manager",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **model_kwargs,
) -> Agent:
    """Get the release manager agent with optional model parameters.

    Args:
        agent_name: The name of the agent (defaults to "release-manager" for backward compatibility)
        temperature: Model temperature (0.0-2.0)
        max_tokens: Maximum tokens in response
        **model_kwargs: Additional model parameters

    Returns:
        Agent instance

    Raises:
        KeyError: If the agent name is not "release-manager"
    """
    if agent_name != "release-manager":
        raise KeyError(
            f"Agent '{agent_name}' not found. "
            f"Only 'release-manager' agent is available."
        )

    return create_release_manager(
        temperature=temperature, max_tokens=max_tokens, **model_kwargs
    )
