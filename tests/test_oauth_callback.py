"""Tests for OAuth callback service and state validation.

These tests cover:
- Successful OAuth flows (Google Drive, GitHub)
- Invalid authorization codes
- Provider configuration errors
- Network failures and timeouts
- State token validation (CSRF protection)
- State token expiration
"""

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests
from google.auth.exceptions import GoogleAuthError

from agentllm.oauth_callback.providers import GitHubProvider, GoogleDriveProvider, ProviderRegistry
from agentllm.oauth_callback.state_validation import (
    StateTokenError,
    StateTokenExpiredError,
    StateTokenInvalidError,
    generate_state_token,
    validate_state_token,
)

# ============================================================================
# State Token Validation Tests
# ============================================================================


class TestStateTokenValidation:
    """Tests for OAuth state token generation and validation."""

    def test_generate_and_validate_state_token(self):
        """Test successful state token generation and validation."""
        user_id = "test_user_123"

        # Generate token
        token = generate_state_token(user_id)
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

        # Validate token
        validated_user_id = validate_state_token(token)
        assert validated_user_id == user_id

    def test_validate_invalid_state_token(self):
        """Test validation fails with invalid token."""
        invalid_token = "invalid.jwt.token"

        with pytest.raises(StateTokenInvalidError) as exc_info:
            validate_state_token(invalid_token)

        assert "Invalid" in str(exc_info.value) or "CSRF" in str(exc_info.value)

    def test_validate_expired_state_token(self):
        """Test validation fails with expired token."""
        import jwt

        # Get the secret key from the state_validation module
        from agentllm.oauth_callback import state_validation

        secret_key = state_validation._STATE_SECRET_KEY

        # Create an expired token (expired 1 hour ago)
        expiry = datetime.now(UTC) - timedelta(hours=1)
        payload = {
            "user_id": "test_user",
            "exp": expiry,
            "iat": datetime.now(UTC) - timedelta(hours=2),
        }

        expired_token = jwt.encode(payload, secret_key, algorithm="HS256")

        with pytest.raises(StateTokenExpiredError) as exc_info:
            validate_state_token(expired_token)

        assert "expired" in str(exc_info.value).lower()

    def test_validate_malformed_state_token(self):
        """Test validation fails with malformed token."""
        malformed_tokens = [
            "",
            "not-a-jwt",
            "a.b",  # Too few parts
            "a.b.c.d",  # Too many parts
        ]

        for token in malformed_tokens:
            with pytest.raises(StateTokenError):
                validate_state_token(token)


# ============================================================================
# Google Drive Provider Tests
# ============================================================================


class TestGoogleDriveProvider:
    """Tests for Google Drive OAuth provider."""

    @pytest.fixture
    def mock_token_storage(self):
        """Mock TokenStorage for testing."""
        storage = MagicMock()
        storage.upsert_token.return_value = True
        return storage

    @pytest.fixture
    def gdrive_provider(self, mock_token_storage):
        """Google Drive provider with mocked dependencies."""
        with patch.dict(
            os.environ,
            {
                "GDRIVE_CLIENT_ID": "test_client_id",
                "GDRIVE_CLIENT_SECRET": "test_client_secret",
            },
        ):
            return GoogleDriveProvider(token_storage=mock_token_storage)

    def test_provider_name(self, gdrive_provider):
        """Test provider returns correct name."""
        assert gdrive_provider.get_provider_name() == "google"

    def test_is_configured_with_credentials(self, gdrive_provider):
        """Test provider is configured when credentials are set."""
        assert gdrive_provider.is_configured() is True

    def test_is_not_configured_without_credentials(self, mock_token_storage):
        """Test provider is not configured when credentials are missing."""
        with patch.dict(os.environ, {}, clear=True):
            provider = GoogleDriveProvider(token_storage=mock_token_storage)
            assert provider.is_configured() is False

    def test_successful_oauth_flow(self, gdrive_provider, mock_token_storage):
        """Test successful Google Drive OAuth code exchange."""
        user_id = "test_user"
        state_token = generate_state_token(user_id)
        code = "test_auth_code"
        redirect_uri = "http://localhost:8501/callback"

        # Mock the OAuth flow
        mock_credentials = MagicMock()
        mock_credentials.token = "access_token_123"
        mock_credentials.refresh_token = "refresh_token_123"
        mock_credentials.expiry = datetime.now(UTC) + timedelta(hours=1)
        mock_credentials.scopes = ["https://www.googleapis.com/auth/drive.readonly"]

        with patch("agentllm.oauth_callback.providers.Flow") as mock_flow_class:
            mock_flow = MagicMock()
            mock_flow.credentials = mock_credentials
            mock_flow_class.from_client_config.return_value = mock_flow

            success, message = gdrive_provider.exchange_code_for_token(code, state_token, redirect_uri)

            assert success is True
            assert "Successfully authenticated" in message
            assert user_id in message
            mock_token_storage.upsert_token.assert_called_once_with(
                "gdrive",
                user_id=user_id,
                credentials=mock_credentials,
            )

    def test_oauth_flow_with_invalid_state_token(self, gdrive_provider):
        """Test OAuth flow fails with invalid state token (CSRF protection)."""
        invalid_state = "invalid_state_token"
        code = "test_auth_code"
        redirect_uri = "http://localhost:8501/callback"

        success, message = gdrive_provider.exchange_code_for_token(code, invalid_state, redirect_uri)

        assert success is False
        assert "Invalid authorization request" in message or "Authorization failed" in message

    def test_oauth_flow_with_expired_state_token(self, gdrive_provider):
        """Test OAuth flow fails with expired state token."""
        import jwt

        # Get the secret key from the state_validation module
        from agentllm.oauth_callback import state_validation

        secret_key = state_validation._STATE_SECRET_KEY

        # Create expired token
        expiry = datetime.now(UTC) - timedelta(hours=1)
        payload = {
            "user_id": "test_user",
            "exp": expiry,
            "iat": datetime.now(UTC) - timedelta(hours=2),
        }
        expired_token = jwt.encode(payload, secret_key, algorithm="HS256")

        code = "test_auth_code"
        redirect_uri = "http://localhost:8501/callback"

        success, message = gdrive_provider.exchange_code_for_token(code, expired_token, redirect_uri)

        assert success is False
        assert "expired" in message.lower() or "try again" in message.lower()

    def test_oauth_flow_with_invalid_code(self, gdrive_provider):
        """Test OAuth flow fails with invalid authorization code."""
        user_id = "test_user"
        state_token = generate_state_token(user_id)
        invalid_code = "invalid_code"
        redirect_uri = "http://localhost:8501/callback"

        with patch("agentllm.oauth_callback.providers.Flow") as mock_flow_class:
            mock_flow = MagicMock()
            mock_flow.fetch_token.side_effect = GoogleAuthError("Invalid authorization code")
            mock_flow_class.from_client_config.return_value = mock_flow

            success, message = gdrive_provider.exchange_code_for_token(invalid_code, state_token, redirect_uri)

            assert success is False
            assert "Google authentication failed" in message or "try again" in message.lower()

    def test_oauth_flow_with_network_timeout(self, gdrive_provider):
        """Test OAuth flow handles network timeouts."""
        user_id = "test_user"
        state_token = generate_state_token(user_id)
        code = "test_auth_code"
        redirect_uri = "http://localhost:8501/callback"

        with patch("agentllm.oauth_callback.providers.Flow") as mock_flow_class:
            mock_flow = MagicMock()
            mock_flow.fetch_token.side_effect = requests.exceptions.Timeout("Request timed out")
            mock_flow_class.from_client_config.return_value = mock_flow

            success, message = gdrive_provider.exchange_code_for_token(code, state_token, redirect_uri)

            assert success is False
            assert "timed out" in message.lower() or "try again" in message.lower()

    def test_oauth_flow_with_database_failure(self, gdrive_provider, mock_token_storage):
        """Test OAuth flow handles database storage failures."""
        user_id = "test_user"
        state_token = generate_state_token(user_id)
        code = "test_auth_code"
        redirect_uri = "http://localhost:8501/callback"

        # Mock successful OAuth but failed database storage
        mock_credentials = MagicMock()
        mock_credentials.token = "access_token_123"
        mock_credentials.refresh_token = "refresh_token_123"
        mock_credentials.expiry = datetime.now(UTC) + timedelta(hours=1)
        mock_credentials.scopes = ["https://www.googleapis.com/auth/drive.readonly"]

        mock_token_storage.upsert_token.return_value = False

        with patch("agentllm.oauth_callback.providers.Flow") as mock_flow_class:
            mock_flow = MagicMock()
            mock_flow.credentials = mock_credentials
            mock_flow_class.from_client_config.return_value = mock_flow

            success, message = gdrive_provider.exchange_code_for_token(code, state_token, redirect_uri)

            assert success is False
            assert "Failed to save credentials" in message


# ============================================================================
# GitHub Provider Tests
# ============================================================================


class TestGitHubProvider:
    """Tests for GitHub OAuth provider."""

    @pytest.fixture
    def mock_token_storage(self):
        """Mock TokenStorage for testing."""
        storage = MagicMock()
        storage.upsert_token.return_value = True
        return storage

    @pytest.fixture
    def github_provider(self, mock_token_storage):
        """GitHub provider with mocked dependencies."""
        with patch.dict(
            os.environ,
            {
                "GITHUB_CLIENT_ID": "test_client_id",
                "GITHUB_CLIENT_SECRET": "test_client_secret",
            },
        ):
            return GitHubProvider(token_storage=mock_token_storage)

    def test_provider_name(self, github_provider):
        """Test provider returns correct name."""
        assert github_provider.get_provider_name() == "github"

    def test_is_configured_with_credentials(self, github_provider):
        """Test provider is configured when credentials are set."""
        assert github_provider.is_configured() is True

    def test_successful_oauth_flow(self, github_provider, mock_token_storage):
        """Test successful GitHub OAuth code exchange."""
        user_id = "test_user"
        state_token = generate_state_token(user_id)
        code = "test_auth_code"
        redirect_uri = "http://localhost:8501/callback"

        # Mock the token exchange request
        mock_token_response = Mock()
        mock_token_response.json.return_value = {
            "access_token": "gho_test_token_123",
            "token_type": "bearer",
            "scope": "repo,user",
        }
        mock_token_response.raise_for_status = Mock()

        # Mock the user info request
        mock_user_response = Mock()
        mock_user_response.json.return_value = {
            "login": "testuser",
            "id": 12345,
        }
        mock_user_response.raise_for_status = Mock()

        with patch("agentllm.oauth_callback.providers.requests") as mock_requests:
            mock_requests.post.return_value = mock_token_response
            mock_requests.get.return_value = mock_user_response
            mock_requests.exceptions = requests.exceptions

            success, message = github_provider.exchange_code_for_token(code, state_token, redirect_uri)

            assert success is True
            assert "Successfully authenticated" in message
            assert "testuser" in message
            mock_token_storage.upsert_token.assert_called_once()

            # Verify timeout was set on requests
            post_call_kwargs = mock_requests.post.call_args[1]
            assert "timeout" in post_call_kwargs
            assert post_call_kwargs["timeout"] == 10

            get_call_kwargs = mock_requests.get.call_args[1]
            assert "timeout" in get_call_kwargs
            assert get_call_kwargs["timeout"] == 10

    def test_oauth_flow_with_timeout(self, github_provider):
        """Test OAuth flow handles request timeouts."""
        user_id = "test_user"
        state_token = generate_state_token(user_id)
        code = "test_auth_code"
        redirect_uri = "http://localhost:8501/callback"

        with patch("agentllm.oauth_callback.providers.requests") as mock_requests:
            mock_requests.post.side_effect = requests.exceptions.Timeout("Request timed out")
            mock_requests.exceptions = requests.exceptions

            success, message = github_provider.exchange_code_for_token(code, state_token, redirect_uri)

            assert success is False
            assert "timed out" in message.lower()

    def test_oauth_flow_with_http_error(self, github_provider):
        """Test OAuth flow handles HTTP errors."""
        user_id = "test_user"
        state_token = generate_state_token(user_id)
        code = "test_auth_code"
        redirect_uri = "http://localhost:8501/callback"

        with patch("agentllm.oauth_callback.providers.requests") as mock_requests:
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Unauthorized")
            mock_requests.post.return_value = mock_response
            mock_requests.exceptions = requests.exceptions

            success, message = github_provider.exchange_code_for_token(code, state_token, redirect_uri)

            assert success is False
            assert "GitHub authorization failed" in message or "try again" in message.lower()

    def test_oauth_flow_with_github_error_response(self, github_provider):
        """Test OAuth flow handles GitHub error responses."""
        user_id = "test_user"
        state_token = generate_state_token(user_id)
        code = "invalid_code"
        redirect_uri = "http://localhost:8501/callback"

        mock_response = Mock()
        mock_response.json.return_value = {
            "error": "bad_verification_code",
            "error_description": "The code passed is incorrect or expired.",
        }
        mock_response.raise_for_status = Mock()

        with patch("agentllm.oauth_callback.providers.requests") as mock_requests:
            mock_requests.post.return_value = mock_response
            mock_requests.exceptions = requests.exceptions

            success, message = github_provider.exchange_code_for_token(code, state_token, redirect_uri)

            assert success is False
            assert "GitHub authorization failed" in message or "try again" in message.lower()


# ============================================================================
# Provider Registry Tests
# ============================================================================


class TestProviderRegistry:
    """Tests for OAuth provider registry."""

    @pytest.fixture
    def mock_token_storage(self):
        """Mock TokenStorage for testing."""
        return MagicMock()

    def test_registry_initialization(self, mock_token_storage):
        """Test provider registry initializes with built-in providers."""
        with patch.dict(
            os.environ,
            {
                "GDRIVE_CLIENT_ID": "test_gdrive_id",
                "GDRIVE_CLIENT_SECRET": "test_gdrive_secret",
                "GITHUB_CLIENT_ID": "test_github_id",
                "GITHUB_CLIENT_SECRET": "test_github_secret",
            },
        ):
            registry = ProviderRegistry(token_storage=mock_token_storage)

            # Check providers are registered
            assert registry.get_provider("google") is not None
            assert registry.get_provider("github") is not None
            assert isinstance(registry.get_provider("google"), GoogleDriveProvider)
            assert isinstance(registry.get_provider("github"), GitHubProvider)

    def test_get_configured_providers(self, mock_token_storage):
        """Test get_configured_providers returns only configured providers."""
        with patch.dict(
            os.environ,
            {
                "GDRIVE_CLIENT_ID": "test_gdrive_id",
                "GDRIVE_CLIENT_SECRET": "test_gdrive_secret",
                # GitHub credentials not set
            },
            clear=True,
        ):
            registry = ProviderRegistry(token_storage=mock_token_storage)

            configured = registry.get_configured_providers()
            assert "google" in configured
            assert "github" not in configured

    def test_get_unknown_provider(self, mock_token_storage):
        """Test get_provider returns None for unknown provider."""
        registry = ProviderRegistry(token_storage=mock_token_storage)
        assert registry.get_provider("unknown_provider") is None
