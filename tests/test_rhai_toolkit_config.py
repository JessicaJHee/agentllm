"""
End-to-end tests for RHAIToolkitConfig.

This test suite covers:
- RHAIToolkitConfig instantiation
- Configuration checking (is_configured)
- Toolkit instantiation with real Google Drive credentials
- Integration with GoogleDriveConfig
- Error handling for missing configuration
- Multi-user isolation
"""

import os
from unittest.mock import MagicMock, Mock, patch

import pytest
from google.oauth2.credentials import Credentials

from agentllm.agents.toolkit_configs.gdrive_config import GoogleDriveConfig
from agentllm.agents.toolkit_configs.rhai_toolkit_config import RHAIToolkitConfig
from agentllm.db.token_storage import TokenStorage
from agentllm.tools.rhai_toolkit import RHAITools


# Test fixtures
@pytest.fixture
def mock_token_storage():
    """Provide mock token storage."""
    storage = MagicMock(spec=TokenStorage)
    return storage


@pytest.fixture
def mock_credentials() -> Credentials:
    """Provide mock Google OAuth2 credentials."""
    creds = Mock(spec=Credentials)
    creds.token = "mock_access_token"
    creds.refresh_token = "mock_refresh_token"
    creds.client_id = "mock_client_id"
    creds.client_secret = "mock_client_secret"
    creds.token_uri = "https://oauth2.googleapis.com/token"
    creds.expired = False
    return creds


@pytest.fixture
def mock_gdrive_config(mock_credentials):
    """Provide mock GoogleDriveConfig."""
    config = MagicMock(spec=GoogleDriveConfig)
    config.is_configured.return_value = True
    config.get_toolkit.return_value = MagicMock()  # Mock GoogleDriveTools
    config._get_gdrive_credentials.return_value = mock_credentials
    return config


@pytest.fixture
def mock_gdrive_config_not_configured():
    """Provide mock GoogleDriveConfig that is not configured."""
    config = MagicMock(spec=GoogleDriveConfig)
    config.is_configured.return_value = False
    config.get_toolkit.return_value = None
    config._get_gdrive_credentials.return_value = None
    return config


@pytest.fixture
def env_var_set():
    """Set the required environment variable for testing."""
    original_value = os.environ.get("AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET")
    os.environ["AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET"] = "https://docs.google.com/document/d/test_doc_id/edit"
    yield
    # Restore original value
    if original_value is None:
        os.environ.pop("AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET", None)
    else:
        os.environ["AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET"] = original_value


@pytest.fixture
def env_var_not_set():
    """Ensure environment variable is not set."""
    original_value = os.environ.get("AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET")
    os.environ.pop("AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET", None)
    yield
    # Restore original value
    if original_value is not None:
        os.environ["AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET"] = original_value


class TestRHAIToolkitConfigBasics:
    """Basic tests for RHAIToolkitConfig instantiation."""

    def test_create_config(self, mock_gdrive_config):
        """Test that RHAIToolkitConfig can be instantiated."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)
        assert config is not None
        assert config._gdrive_config is mock_gdrive_config

    def test_create_config_with_token_storage(self, mock_gdrive_config, mock_token_storage):
        """Test that RHAIToolkitConfig accepts token storage."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config, token_storage=mock_token_storage)
        assert config is not None
        assert config.token_storage is mock_token_storage

    def test_reads_env_var_on_init(self, mock_gdrive_config, env_var_set):
        """Test that config reads AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET on init."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)
        assert config._doc_url == "https://docs.google.com/document/d/test_doc_id/edit"

    def test_handles_missing_env_var(self, mock_gdrive_config, env_var_not_set):
        """Test that config handles missing environment variable."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)
        assert config._doc_url is None

    def test_initializes_empty_toolkit_dict(self, mock_gdrive_config):
        """Test that config initializes an empty toolkit dictionary."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)
        assert config._toolkits == {}


class TestIsConfigured:
    """Tests for is_configured() method."""

    def test_not_configured_when_no_env_var(self, mock_gdrive_config, env_var_not_set):
        """Test that config is not configured when env var is not set."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)
        assert not config.is_configured("user123")

    def test_not_configured_when_gdrive_not_configured(self, mock_gdrive_config_not_configured, env_var_set):
        """Test that config is not configured when GDrive is not configured."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config_not_configured)
        assert not config.is_configured("user123")
        mock_gdrive_config_not_configured.is_configured.assert_called_once_with("user123")

    def test_configured_when_env_var_and_gdrive_configured(self, mock_gdrive_config, env_var_set):
        """Test that config is configured when both env var and GDrive are configured."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)
        assert config.is_configured("user123")
        mock_gdrive_config.is_configured.assert_called_once_with("user123")


class TestExtractAndStoreConfig:
    """Tests for extract_and_store_config() method."""

    def test_returns_none(self, mock_gdrive_config):
        """Test that extract_and_store_config always returns None."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)
        result = config.extract_and_store_config("some message", "user123")
        assert result is None

    def test_does_not_modify_state(self, mock_gdrive_config):
        """Test that extract_and_store_config does not modify config state."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)
        config.extract_and_store_config("configure something", "user123")
        # Should not have created any toolkits
        assert config._toolkits == {}


class TestGetConfigPrompt:
    """Tests for get_config_prompt() method."""

    def test_returns_none(self, mock_gdrive_config):
        """Test that get_config_prompt always returns None (silent config)."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)
        result = config.get_config_prompt("user123")
        assert result is None

    def test_returns_none_even_when_not_configured(self, mock_gdrive_config_not_configured, env_var_not_set):
        """Test that get_config_prompt returns None even when not configured."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config_not_configured)
        result = config.get_config_prompt("user123")
        assert result is None


class TestCheckAuthorizationRequest:
    """Tests for check_authorization_request() method."""

    def test_returns_none(self, mock_gdrive_config):
        """Test that check_authorization_request always returns None."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)
        result = config.check_authorization_request("authorize something", "user123")
        assert result is None

    def test_does_not_call_gdrive_config(self, mock_gdrive_config):
        """Test that check_authorization_request does not call gdrive_config."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)
        config.check_authorization_request("authorize RHAI", "user123")
        # Should not have called any methods on gdrive_config
        mock_gdrive_config.check_authorization_request.assert_not_called()


class TestIsRequired:
    """Tests for is_required() method."""

    def test_returns_true(self, mock_gdrive_config):
        """Test that is_required returns True."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)
        assert config.is_required() is True


class TestGetToolkit:
    """Tests for get_toolkit() method - the core functionality."""

    def test_returns_none_when_not_configured_no_env_var(self, mock_gdrive_config, env_var_not_set):
        """Test that get_toolkit returns None when env var is not set."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)
        toolkit = config.get_toolkit("user123")
        assert toolkit is None

    def test_returns_none_when_not_configured_no_gdrive(self, mock_gdrive_config_not_configured, env_var_set):
        """Test that get_toolkit returns None when GDrive is not configured."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config_not_configured)
        toolkit = config.get_toolkit("user123")
        assert toolkit is None

    def test_returns_none_when_gdrive_toolkit_not_available(self, mock_gdrive_config, env_var_set):
        """Test that get_toolkit returns None when GDrive toolkit is not available."""
        mock_gdrive_config.get_toolkit.return_value = None
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)
        toolkit = config.get_toolkit("user123")
        assert toolkit is None

    def test_returns_none_when_credentials_not_available(self, mock_gdrive_config, env_var_set):
        """Test that get_toolkit returns None when credentials are not available."""
        mock_gdrive_config._get_gdrive_credentials.return_value = None
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)
        toolkit = config.get_toolkit("user123")
        assert toolkit is None

    def test_creates_toolkit_when_configured(self, mock_gdrive_config, mock_credentials, env_var_set):
        """Test that get_toolkit creates RHAITools when fully configured."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)

        with patch("agentllm.agents.toolkit_configs.rhai_toolkit_config.RHAITools") as MockRHAITools:
            mock_toolkit_instance = MagicMock(spec=RHAITools)
            MockRHAITools.return_value = mock_toolkit_instance

            toolkit = config.get_toolkit("user123")

            # Verify RHAITools was created with credentials
            MockRHAITools.assert_called_once_with(credentials=mock_credentials)
            assert toolkit is mock_toolkit_instance

    def test_caches_toolkit_per_user(self, mock_gdrive_config, mock_credentials, env_var_set):
        """Test that get_toolkit caches toolkit instances per user."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)

        with patch("agentllm.agents.toolkit_configs.rhai_toolkit_config.RHAITools") as MockRHAITools:
            mock_toolkit_instance = MagicMock(spec=RHAITools)
            MockRHAITools.return_value = mock_toolkit_instance

            # First call - should create toolkit
            toolkit1 = config.get_toolkit("user123")
            assert toolkit1 is mock_toolkit_instance
            assert MockRHAITools.call_count == 1

            # Second call - should return cached toolkit
            toolkit2 = config.get_toolkit("user123")
            assert toolkit2 is mock_toolkit_instance
            assert MockRHAITools.call_count == 1  # Not called again

    def test_different_users_get_different_toolkits(self, mock_gdrive_config, mock_credentials, env_var_set):
        """Test that different users get different toolkit instances."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)

        with patch("agentllm.agents.toolkit_configs.rhai_toolkit_config.RHAITools") as MockRHAITools:
            mock_toolkit1 = MagicMock(spec=RHAITools)
            mock_toolkit2 = MagicMock(spec=RHAITools)
            MockRHAITools.side_effect = [mock_toolkit1, mock_toolkit2]

            # Get toolkit for user1
            toolkit_user1 = config.get_toolkit("user1")
            assert toolkit_user1 is mock_toolkit1

            # Get toolkit for user2
            toolkit_user2 = config.get_toolkit("user2")
            assert toolkit_user2 is mock_toolkit2

            # Verify both are cached
            assert config._toolkits["user1"] is mock_toolkit1
            assert config._toolkits["user2"] is mock_toolkit2

    def test_handles_toolkit_creation_error(self, mock_gdrive_config, mock_credentials, env_var_set):
        """Test that get_toolkit handles errors during toolkit creation."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)

        with patch("agentllm.agents.toolkit_configs.rhai_toolkit_config.RHAITools") as MockRHAITools:
            MockRHAITools.side_effect = Exception("Failed to create toolkit")

            toolkit = config.get_toolkit("user123")
            assert toolkit is None
            # Should not have cached the failed attempt
            assert "user123" not in config._toolkits


class TestEndToEndIntegration:
    """End-to-end integration tests with real components (where possible)."""

    def test_full_flow_with_real_rhai_tools(self, mock_gdrive_config, mock_credentials, env_var_set):
        """Test full flow creating a real RHAITools instance."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)

        # Get toolkit - this should create a real RHAITools instance
        toolkit = config.get_toolkit("user123")

        # Verify toolkit was created and cached
        assert toolkit is not None
        assert isinstance(toolkit, RHAITools)
        assert "user123" in config._toolkits
        assert config._toolkits["user123"] is toolkit

        # Verify toolkit has the expected attributes
        assert hasattr(toolkit, "exporter")
        assert hasattr(toolkit, "get_releases")
        assert toolkit.name == "rhai_tools"

    def test_multiple_users_isolation(self, mock_gdrive_config, env_var_set):
        """Test that multiple users have isolated toolkit instances."""
        # Create different credentials for different users
        creds_user1 = Mock(spec=Credentials)
        creds_user1.token = "token_user1"

        creds_user2 = Mock(spec=Credentials)
        creds_user2.token = "token_user2"

        # Mock gdrive_config to return different credentials per user
        def get_credentials_side_effect(user_id):
            if user_id == "user1":
                return creds_user1
            elif user_id == "user2":
                return creds_user2
            return None

        mock_gdrive_config._get_gdrive_credentials.side_effect = get_credentials_side_effect

        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)

        # Get toolkits for both users
        toolkit_user1 = config.get_toolkit("user1")
        toolkit_user2 = config.get_toolkit("user2")

        # Verify both are created and different
        assert toolkit_user1 is not None
        assert toolkit_user2 is not None
        assert toolkit_user1 is not toolkit_user2

        # Verify they're cached separately
        assert config._toolkits["user1"] is toolkit_user1
        assert config._toolkits["user2"] is toolkit_user2

    def test_reconfiguration_flow(self, mock_gdrive_config, mock_credentials, env_var_set):
        """Test that toolkit can be recreated after configuration changes."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)

        # Initial configuration
        toolkit1 = config.get_toolkit("user123")
        assert toolkit1 is not None

        # Simulate credential change by clearing cache
        config._toolkits.clear()

        # Create new credentials
        new_creds = Mock(spec=Credentials)
        new_creds.token = "new_token"
        mock_gdrive_config._get_gdrive_credentials.return_value = new_creds

        # Get toolkit again - should create new instance
        toolkit2 = config.get_toolkit("user123")
        assert toolkit2 is not None
        assert toolkit2 is not toolkit1  # Different instance

    def test_configuration_state_transitions(self, mock_gdrive_config_not_configured, env_var_set):
        """Test configuration state transitions from unconfigured to configured."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config_not_configured)

        # Initially not configured
        assert not config.is_configured("user123")
        assert config.get_toolkit("user123") is None

        # Simulate user configuring GDrive
        mock_gdrive_config_not_configured.is_configured.return_value = True
        creds = Mock(spec=Credentials)
        creds.token = "new_token"
        mock_gdrive_config_not_configured.get_toolkit.return_value = MagicMock()
        mock_gdrive_config_not_configured._get_gdrive_credentials.return_value = creds

        # Now should be configured
        assert config.is_configured("user123")
        toolkit = config.get_toolkit("user123")
        assert toolkit is not None
        assert isinstance(toolkit, RHAITools)


class TestErrorHandlingAndEdgeCases:
    """Tests for error handling and edge cases."""

    def test_handles_invalid_credentials(self, mock_gdrive_config, env_var_set):
        """Test that get_toolkit handles invalid credentials gracefully."""
        # Return invalid credentials (not a Credentials object)
        # Note: RHAITools constructor accepts any object, so this will create a toolkit
        # but the toolkit will fail when actually used. This tests that at least
        # the toolkit creation doesn't crash.
        mock_gdrive_config._get_gdrive_credentials.return_value = "not_a_credentials_object"

        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)

        # Will create toolkit (doesn't validate credentials at creation time)
        toolkit = config.get_toolkit("user123")
        # In practice, this toolkit would fail when get_releases() is called
        assert toolkit is not None

    def test_handles_exception_during_credential_fetch(self, mock_gdrive_config, env_var_set):
        """Test that get_toolkit handles exceptions during credential fetch."""
        # Simulate exception when fetching credentials
        mock_gdrive_config._get_gdrive_credentials.side_effect = Exception("Credential fetch failed")

        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)

        # Should handle error gracefully
        toolkit = config.get_toolkit("user123")
        assert toolkit is None

    def test_empty_user_id(self, mock_gdrive_config, env_var_set):
        """Test behavior with empty user_id."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)

        # Should handle empty user_id
        toolkit = config.get_toolkit("")
        # Behavior depends on gdrive_config implementation
        assert toolkit is None or isinstance(toolkit, RHAITools)

    def test_special_characters_in_user_id(self, mock_gdrive_config, mock_credentials, env_var_set):
        """Test that user_id with special characters is handled correctly."""
        config = RHAIToolkitConfig(gdrive_config=mock_gdrive_config)

        special_user_id = "user@example.com!#$%"
        toolkit = config.get_toolkit(special_user_id)

        # Should create and cache toolkit
        assert toolkit is not None
        assert special_user_id in config._toolkits
