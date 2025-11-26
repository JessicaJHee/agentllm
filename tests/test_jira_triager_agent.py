"""
Tests for the Jira Triager Agent.

This test suite demonstrates testing patterns for:
- Agent instantiation and configuration
- Jira authentication flow
- Toolkit dependencies
- Basic agent behavior
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from agno.db.sqlite import SqliteDb
from dotenv import load_dotenv

from agentllm.agents.jira_triager import JiraTriager
from agentllm.agents.jira_triager_configurator import JiraTriagerConfigurator
from agentllm.agents.jira_triager_toolkit_config import JiraTriagerToolkitConfig
from agentllm.agents.toolkit_configs.jira_config import JiraConfig
from agentllm.db import TokenStorage
from agentllm.db.token_storage import TokenStorage as TokenStorageType

# Load .env file for tests
load_dotenv()

# Map GEMINI_API_KEY to GOOGLE_API_KEY if needed
if "GOOGLE_API_KEY" not in os.environ and "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


# Test fixtures
@pytest.fixture
def shared_db() -> SqliteDb:
    """Provide a shared test database."""
    db_path = Path("tmp/test_jira_triager.db")
    db_path.parent.mkdir(exist_ok=True)
    db = SqliteDb(db_file=str(db_path))
    yield db
    # Cleanup after tests
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def token_storage(shared_db: SqliteDb) -> TokenStorageType:
    """Provide a token storage instance."""
    return TokenStorage(agno_db=shared_db)


@pytest.fixture
def mock_jira_token() -> str:
    """Provide a mock Jira token for testing."""
    return "mock_jira_token_123456"


@pytest.fixture
def mock_jira_url() -> str:
    """Provide a mock Jira URL for testing."""
    return "https://issues.example.com"


class TestJiraTriagerBasics:
    """Basic tests for JiraTriager instantiation and parameters."""

    def test_create_agent(self, shared_db: SqliteDb, token_storage: TokenStorageType):
        """Test that JiraTriager can be instantiated."""
        agent = JiraTriager(shared_db=shared_db, token_storage=token_storage, user_id="test-user")
        assert agent is not None

        # Test configurator separately
        configurator = JiraTriagerConfigurator(user_id="test-user", session_id=None, shared_db=shared_db, token_storage=token_storage)
        assert len(configurator.toolkit_configs) > 0

    def test_create_agent_with_params(self, shared_db: SqliteDb, token_storage: TokenStorageType):
        """Test that JiraTriager accepts model parameters."""
        agent = JiraTriager(shared_db=shared_db, token_storage=token_storage, user_id="test-user", temperature=0.7, max_tokens=200)
        assert agent is not None

        # Test configurator parameters separately
        configurator = JiraTriagerConfigurator(
            user_id="test-user", session_id=None, shared_db=shared_db, token_storage=token_storage, temperature=0.7, max_tokens=200
        )
        assert configurator._temperature == 0.7
        assert configurator._max_tokens == 200

    def test_toolkit_configs_initialized(self, shared_db: SqliteDb, token_storage: TokenStorageType):
        """Test that toolkit configs are properly initialized."""
        configurator = JiraTriagerConfigurator(user_id="test-user", session_id=None, shared_db=shared_db, token_storage=token_storage)
        assert hasattr(configurator, "toolkit_configs")
        assert isinstance(configurator.toolkit_configs, list)
        # Should have exactly 4 configs: GoogleDrive, Jira, JiraTriager, SystemPromptExtension
        assert len(configurator.toolkit_configs) == 4

    def test_jira_configs_present(self, shared_db: SqliteDb, token_storage: TokenStorageType):
        """Test that Jira-related configs are present."""
        configurator = JiraTriagerConfigurator(user_id="test-user", session_id=None, shared_db=shared_db, token_storage=token_storage)

        # Check for JiraConfig
        jira_config_present = any(isinstance(config, JiraConfig) for config in configurator.toolkit_configs)
        assert jira_config_present

        # Check for JiraTriagerToolkitConfig
        triager_config_present = any(isinstance(config, JiraTriagerToolkitConfig) for config in configurator.toolkit_configs)
        assert triager_config_present

    def test_jira_triager_config_is_required(self, shared_db: SqliteDb, token_storage: TokenStorageType):
        """Test that JiraTriagerToolkitConfig is marked as required."""
        configurator = JiraTriagerConfigurator(user_id="test-user", session_id=None, shared_db=shared_db, token_storage=token_storage)
        triager_config = next((c for c in configurator.toolkit_configs if isinstance(c, JiraTriagerToolkitConfig)), None)
        assert triager_config is not None
        assert triager_config.is_required() is True


class TestJiraAuthentication:
    """Tests for Jira authentication flow."""

    def test_prompts_for_jira_when_not_configured(self, shared_db: SqliteDb, token_storage: TokenStorageType):
        """Test that agent prompts for required config when not configured.

        Note: Configs are checked in order. Google Drive comes first (like Release Manager),
        so when neither is configured, Google Drive is prompted first.
        """
        agent = JiraTriager(shared_db=shared_db, token_storage=token_storage, user_id="test-user")
        user_id = "test-user-no-config"

        # User sends message without configuring anything
        response = agent.run("Hello!", user_id=user_id)

        # Should get Google Drive config prompt (first required config)
        content = str(response.content) if hasattr(response, "content") else str(response)
        assert "google drive" in content.lower() or "gdrive" in content.lower()
        assert "oauth" in content.lower() or "configuration" in content.lower()

    @patch("agentllm.tools.jira_toolkit.JIRA")
    def test_jira_token_extraction_and_storage(
        self, mock_jira_class, shared_db: SqliteDb, token_storage: TokenStorageType, mock_jira_token: str
    ):
        """Test that Jira token is extracted and stored correctly."""
        # Mock Jira client to avoid actual API calls
        mock_jira_instance = MagicMock()
        mock_jira_instance.myself.return_value = {"displayName": "Test User"}
        mock_jira_class.return_value = mock_jira_instance

        user_id = "test-user-jira-1"
        agent = JiraTriager(shared_db=shared_db, token_storage=token_storage, user_id=user_id)

        # User provides Jira token
        response = agent.run(f"My Jira token is {mock_jira_token}", user_id=user_id)

        # Should get confirmation
        content = str(response.content) if hasattr(response, "content") else str(response)
        assert "✅" in content or "success" in content.lower() or "configured" in content.lower()

        # Verify token is stored by creating a fresh configurator
        configurator = JiraTriagerConfigurator(user_id=user_id, session_id=None, shared_db=shared_db, token_storage=token_storage)
        jira_config = next((c for c in configurator.toolkit_configs if isinstance(c, JiraConfig)), None)
        assert jira_config is not None
        assert jira_config.is_configured(user_id)


class TestSystemPromptConfiguration:
    """Tests for required Google Drive system prompt configuration."""

    def test_google_drive_config_always_included(self, shared_db: SqliteDb, token_storage: TokenStorageType):
        """Test that GoogleDriveConfig is always included (required)."""
        configurator = JiraTriagerConfigurator(user_id="test-user", session_id=None, shared_db=shared_db, token_storage=token_storage)

        from agentllm.agents.toolkit_configs.gdrive_config import GoogleDriveConfig

        gdrive_configs = [c for c in configurator.toolkit_configs if isinstance(c, GoogleDriveConfig)]
        assert len(gdrive_configs) == 1

    def test_system_prompt_config_always_included(self, shared_db: SqliteDb, token_storage: TokenStorageType):
        """Test that SystemPromptExtensionConfig is always included (required)."""
        configurator = JiraTriagerConfigurator(user_id="test-user", session_id=None, shared_db=shared_db, token_storage=token_storage)

        from agentllm.agents.toolkit_configs.system_prompt_extension_config import SystemPromptExtensionConfig

        system_prompt_configs = [c for c in configurator.toolkit_configs if isinstance(c, SystemPromptExtensionConfig)]
        assert len(system_prompt_configs) == 1

    def test_config_order(self, shared_db: SqliteDb, token_storage: TokenStorageType):
        """Test that configs are in correct order (GoogleDrive before SystemPrompt)."""
        configurator = JiraTriagerConfigurator(user_id="test-user", session_id=None, shared_db=shared_db, token_storage=token_storage)

        from agentllm.agents.toolkit_configs.gdrive_config import GoogleDriveConfig
        from agentllm.agents.toolkit_configs.system_prompt_extension_config import SystemPromptExtensionConfig

        # Find indices
        gdrive_index = next(i for i, c in enumerate(configurator.toolkit_configs) if isinstance(c, GoogleDriveConfig))
        sysprompt_index = next(i for i, c in enumerate(configurator.toolkit_configs) if isinstance(c, SystemPromptExtensionConfig))

        # GoogleDrive must come before SystemPrompt
        assert gdrive_index < sysprompt_index


class TestAgentMetadata:
    """Tests for agent metadata and configuration."""

    def test_agent_name(self, shared_db: SqliteDb, token_storage: TokenStorageType):
        """Test that agent has correct name."""
        configurator = JiraTriagerConfigurator(user_id="test-user", session_id=None, shared_db=shared_db, token_storage=token_storage)
        assert configurator._get_agent_name() == "jira-triager"

    def test_agent_description(self, shared_db: SqliteDb, token_storage: TokenStorageType):
        """Test that agent has a description."""
        configurator = JiraTriagerConfigurator(user_id="test-user", session_id=None, shared_db=shared_db, token_storage=token_storage)
        description = configurator._get_agent_description()
        assert description is not None
        assert len(description) > 0

    def test_agent_instructions(self, shared_db: SqliteDb, token_storage: TokenStorageType):
        """Test that agent has comprehensive instructions."""
        configurator = JiraTriagerConfigurator(user_id="test-user", session_id=None, shared_db=shared_db, token_storage=token_storage)
        instructions = configurator._build_agent_instructions()

        assert isinstance(instructions, list)
        assert len(instructions) > 0

        # Check for key instruction content
        instructions_text = " ".join(instructions).lower()
        assert "jira" in instructions_text
        assert "triage" in instructions_text or "triag" in instructions_text
        assert "component" in instructions_text
        assert "keyword" in instructions_text

    def test_model_params_include_thinking(self, shared_db: SqliteDb, token_storage: TokenStorageType):
        """Test that model params include Gemini thinking configuration."""
        configurator = JiraTriagerConfigurator(user_id="test-user", session_id=None, shared_db=shared_db, token_storage=token_storage)
        model_params = configurator._build_model_params()

        # Check for thinking parameters
        assert "thinking_budget" in model_params
        assert "include_thoughts" in model_params
        assert model_params["thinking_budget"] > 0
        assert model_params["include_thoughts"] is True


class TestToolkitDependencies:
    """Tests for toolkit dependencies and configuration flow."""

    def test_jira_triager_depends_on_jira_config(self, shared_db: SqliteDb, token_storage: TokenStorageType):
        """Test that JiraTriagerToolkitConfig properly depends on JiraConfig."""
        configurator = JiraTriagerConfigurator(user_id="test-user", session_id=None, shared_db=shared_db, token_storage=token_storage)

        jira_config = next((c for c in configurator.toolkit_configs if isinstance(c, JiraConfig)), None)
        triager_config = next((c for c in configurator.toolkit_configs if isinstance(c, JiraTriagerToolkitConfig)), None)

        assert jira_config is not None
        assert triager_config is not None

        # Both should be unconfigured for new user
        test_user = "test-user-deps"
        assert not jira_config.is_configured(test_user)
        assert not triager_config.is_configured(test_user)

    @patch("agentllm.tools.jira_toolkit.JIRA")
    def test_triager_toolkit_available_after_jira_auth(
        self, mock_jira_class, shared_db: SqliteDb, token_storage: TokenStorageType, mock_jira_token: str
    ):
        """Test that Jira config becomes available after Jira auth.

        Note: JiraTriagerToolkitConfig requires BOTH Jira and Google Drive to be configured.
        This test only verifies Jira configuration.
        """
        # Mock Jira client
        mock_jira_instance = MagicMock()
        mock_jira_instance.myself.return_value = {"displayName": "Test User"}
        mock_jira_class.return_value = mock_jira_instance

        user_id = "test-user-toolkit"
        agent = JiraTriager(shared_db=shared_db, token_storage=token_storage, user_id=user_id)

        # Provide Jira token
        agent.run(f"My Jira token is {mock_jira_token}", user_id=user_id)

        # Create fresh configurator to check configuration state
        configurator = JiraTriagerConfigurator(user_id=user_id, session_id=None, shared_db=shared_db, token_storage=token_storage)
        jira_config = next((c for c in configurator.toolkit_configs if isinstance(c, JiraConfig)), None)
        triager_config = next((c for c in configurator.toolkit_configs if isinstance(c, JiraTriagerToolkitConfig)), None)

        assert jira_config.is_configured(user_id)

        # JiraTriagerToolkitConfig requires BOTH Jira and Google Drive
        # Since we only configured Jira, it should NOT be fully configured yet
        assert not triager_config.is_configured(user_id)

        # Jira toolkit should be available
        assert jira_config.get_toolkit(user_id) is not None

        # Triager toolkit should NOT be available yet (needs Google Drive)
        assert triager_config.get_toolkit(user_id) is None


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_agent_handles_empty_message(self, shared_db: SqliteDb, token_storage: TokenStorageType):
        """Test that agent handles empty messages gracefully."""
        agent = JiraTriager(shared_db=shared_db, token_storage=token_storage, user_id="test-user")

        # Should not crash on empty message
        response = agent.run("", user_id="test-user-empty")
        assert response is not None

    def test_agent_handles_multiple_users(self, shared_db: SqliteDb, token_storage: TokenStorageType):
        """Test that agent isolates configurations per user.

        Note: Configs are checked in order. Google Drive comes first (like Release Manager),
        so when neither is configured, Google Drive is prompted first.
        """
        agent = JiraTriager(shared_db=shared_db, token_storage=token_storage, user_id="test-user")

        user1 = "test-user-multi-1"
        user2 = "test-user-multi-2"

        # Both users should start unconfigured
        configurator = JiraTriagerConfigurator(user_id="test-user", session_id=None, shared_db=shared_db, token_storage=token_storage)
        jira_config = next((c for c in configurator.toolkit_configs if isinstance(c, JiraConfig)), None)
        assert not jira_config.is_configured(user1)
        assert not jira_config.is_configured(user2)

        # Both should get independent prompts
        response1 = agent.run("Hello", user_id=user1)
        response2 = agent.run("Hello", user_id=user2)

        content1 = str(response1.content) if hasattr(response1, "content") else str(response1)
        content2 = str(response2.content) if hasattr(response2, "content") else str(response2)

        # Both should get Google Drive configuration prompts (first required config)
        assert "google drive" in content1.lower() or "gdrive" in content1.lower()
        assert "google drive" in content2.lower() or "gdrive" in content2.lower()


# Integration test marker
@pytest.mark.integration
class TestJiraTriagerIntegration:
    """Integration tests that require actual Jira access.

    Run with: pytest tests/test_jira_triager_agent.py -m integration

    These tests are skipped unless running with the integration marker.
    They require:
    - JIRA_URL environment variable
    - JIRA_PERSONAL_TOKEN environment variable
    - Access to a real Jira instance
    """

    @pytest.mark.skipif(not os.getenv("JIRA_PERSONAL_TOKEN"), reason="Requires JIRA_PERSONAL_TOKEN")
    def test_real_jira_connection(self, shared_db: SqliteDb, token_storage: TokenStorageType):
        """Test connection to real Jira instance."""
        agent = JiraTriager(shared_db=shared_db, token_storage=token_storage, user_id="test-user")
        user_id = "test-integration"

        jira_token = os.getenv("JIRA_PERSONAL_TOKEN")
        response = agent.run(f"My Jira token is {jira_token}", user_id=user_id)

        content = str(response.content) if hasattr(response, "content") else str(response)
        assert "✅" in content or "success" in content.lower()
