"""Example Agno agents for testing the LiteLLM provider."""

from pathlib import Path
from typing import Optional

from agno.agent import Agent
from agno.models.google import Gemini
from agno.db.sqlite import SqliteDb

# Shared database for all agents to enable session management
DB_PATH = Path("tmp/agno_sessions.db")
DB_PATH.parent.mkdir(exist_ok=True)
shared_db = SqliteDb(db_file=str(DB_PATH))


def create_echo_agent(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **model_kwargs
) -> Agent:
    """Create a simple echo agent that repeats back what it receives.

    Args:
        temperature: Model temperature (0.0-2.0)
        max_tokens: Maximum tokens in response
        **model_kwargs: Additional model parameters
    """
    model_params = {"id": "gemini-2.5-flash"}
    if temperature is not None:
        model_params["temperature"] = temperature
    if max_tokens is not None:
        model_params["max_tokens"] = max_tokens
    model_params.update(model_kwargs)

    return Agent(
        name="echo",
        model=Gemini(**model_params),
        description="A simple agent that echoes back messages",
        instructions=[
            "You are a helpful assistant that echoes back what users say.",
            "Always be friendly and polite.",
        ],
        markdown=True,
        # Session management
        db=shared_db,
        add_history_to_context=True,
        num_history_runs=10,  # Include last 10 messages
        read_chat_history=True,  # Allow agent to read full history
    )


def create_assistant_agent(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **model_kwargs
) -> Agent:
    """Create a general-purpose assistant agent.

    Args:
        temperature: Model temperature (0.0-2.0)
        max_tokens: Maximum tokens in response
        **model_kwargs: Additional model parameters
    """
    model_params = {"id": "gemini-2.5-flash"}
    if temperature is not None:
        model_params["temperature"] = temperature
    if max_tokens is not None:
        model_params["max_tokens"] = max_tokens
    model_params.update(model_kwargs)

    return Agent(
        name="assistant",
        model=Gemini(**model_params),
        description="A helpful general-purpose assistant",
        instructions=[
            "You are a helpful AI assistant.",
            "Provide clear, concise, and accurate responses.",
            "Be friendly and professional.",
        ],
        markdown=True,
        # Session management
        db=shared_db,
        add_history_to_context=True,
        num_history_runs=10,  # Include last 10 messages
        read_chat_history=True,  # Allow agent to read full history
    )


def create_code_agent(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **model_kwargs
) -> Agent:
    """Create a coding assistant agent.

    Args:
        temperature: Model temperature (0.0-2.0)
        max_tokens: Maximum tokens in response
        **model_kwargs: Additional model parameters
    """
    model_params = {"id": "gemini-2.5-flash"}
    if temperature is not None:
        model_params["temperature"] = temperature
    if max_tokens is not None:
        model_params["max_tokens"] = max_tokens
    model_params.update(model_kwargs)

    return Agent(
        name="code-helper",
        model=Gemini(**model_params),
        description="A coding assistant that helps with programming tasks",
        instructions=[
            "You are an expert programming assistant.",
            "Help users with code, debugging, and technical questions.",
            "Provide code examples when appropriate.",
            "Explain concepts clearly.",
        ],
        markdown=True,
        # Session management
        db=shared_db,
        add_history_to_context=True,
        num_history_runs=10,  # Include last 10 messages
        read_chat_history=True,  # Allow agent to read full history
    )


# Registry of available agents
AGENT_REGISTRY = {
    "echo": create_echo_agent,
    "assistant": create_assistant_agent,
    "code-helper": create_code_agent,
}


def get_agent(
    agent_name: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    **model_kwargs
) -> Agent:
    """Get an agent by name with optional model parameters.

    Args:
        agent_name: The name of the agent to retrieve
        temperature: Model temperature (0.0-2.0)
        max_tokens: Maximum tokens in response
        **model_kwargs: Additional model parameters

    Returns:
        Agent instance

    Raises:
        KeyError: If the agent name is not found
    """
    if agent_name not in AGENT_REGISTRY:
        raise KeyError(
            f"Agent '{agent_name}' not found. "
            f"Available agents: {', '.join(AGENT_REGISTRY.keys())}"
        )

    creator_func = AGENT_REGISTRY[agent_name]
    return creator_func(
        temperature=temperature,
        max_tokens=max_tokens,
        **model_kwargs
    )
