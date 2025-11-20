"""Shared fixtures for demo agent accuracy evaluation tests."""

import os
from pathlib import Path

import pytest
from agno.db.sqlite import SqliteDb

from agentllm.agents.demo_agent_configurator import DemoAgentConfigurator
from agentllm.db import TokenStorage
from agentllm.knowledge import KnowledgeManager


# Load environment variables from .env.secrets for tests
def load_env_secrets():
    """Load environment variables from .env.secrets file."""
    env_secrets_path = Path(__file__).parent.parent.parent / ".env.secrets"

    if not env_secrets_path.exists():
        return

    with open(env_secrets_path) as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Parse KEY=VALUE format
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                # Only set if not already in environment
                if key not in os.environ:
                    os.environ[key] = value


# Load .env.secrets at module import time
load_env_secrets()

# Map GEMINI_API_KEY to GOOGLE_API_KEY if not set (same as in demo_agent.py)
if "GOOGLE_API_KEY" not in os.environ and "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


@pytest.fixture
def shared_db(tmp_path):
    """Create file-based test database in temp directory.

    Uses the same pattern as production code (AGENTLLM_DATA_DIR/agno_sessions.db)
    but in a pytest temp directory for test isolation.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        SqliteDb: File-based database instance
    """
    # Use temp directory for test database (same pattern as production)
    db_path = tmp_path / "agno_sessions.db"
    return SqliteDb(db_file=str(db_path))


@pytest.fixture
def token_storage(shared_db):
    """Create token storage for tests.

    Args:
        shared_db: Shared database fixture

    Returns:
        TokenStorage: Token storage instance
    """
    return TokenStorage(agno_db=shared_db)


@pytest.fixture
def knowledge_manager(tmp_path):
    """Create knowledge manager with example knowledge files.

    Uses the actual examples/knowledge/ directory for realistic testing.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        KnowledgeManager: Knowledge manager instance
    """
    # Use actual knowledge files from examples/
    knowledge_path = Path("examples/knowledge")

    # Use temp directory for vector DB to avoid conflicts
    return KnowledgeManager(
        knowledge_path=knowledge_path,
        vector_db_path=tmp_path / "lancedb",
        table_name="test_demo_knowledge",
    )


@pytest.fixture
def demo_configurator(shared_db, token_storage):
    """Create DemoAgentConfigurator for testing.

    This configurator can build Agno agents for evaluation.
    Knowledge loading is handled automatically via _get_knowledge_config().

    Args:
        shared_db: Shared database fixture
        token_storage: Token storage fixture

    Returns:
        DemoAgentConfigurator: Configured instance ready to build agents
    """
    # Clear factory cache to ensure test isolation
    from agentllm.knowledge import KnowledgeManagerFactory

    KnowledgeManagerFactory.clear_cache()

    return DemoAgentConfigurator(
        user_id="test_user",
        session_id="test_session",
        shared_db=shared_db,
        token_storage=token_storage,
    )


@pytest.fixture
def configured_demo_configurator(demo_configurator):
    """Create DemoAgentConfigurator with favorite color already configured.

    This skips the configuration step for tests that don't need to test it.

    Args:
        demo_configurator: Base configurator fixture

    Returns:
        DemoAgentConfigurator: Configurator with color configured
    """
    # Configure favorite color (required toolkit)
    # Use extract_and_store_config with a message containing the color
    demo_configurator.toolkit_configs[0].extract_and_store_config(
        message="my favorite color is blue",
        user_id="test_user",
    )

    return demo_configurator
