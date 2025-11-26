"""OAuth provider registry and implementations.

This module provides a provider registry pattern for handling OAuth callbacks
from multiple providers (Google Drive, GitHub, etc.).
"""

import os
from abc import ABC, abstractmethod

import requests
from google.auth.exceptions import GoogleAuthError
from google_auth_oauthlib.flow import Flow
from loguru import logger

from agentllm.db.token_storage import TokenStorage
from agentllm.oauth_callback.state_validation import (
    StateTokenError,
    StateTokenExpiredError,
    StateTokenInvalidError,
    validate_state_token,
)


class OAuthProvider(ABC):
    """Base class for OAuth providers."""

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the provider name (e.g., 'google', 'github')."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if provider OAuth credentials are configured."""
        pass

    @abstractmethod
    def exchange_code_for_token(self, code: str, state: str, redirect_uri: str) -> tuple[bool, str]:
        """Exchange authorization code for access token and store it.

        Args:
            code: OAuth authorization code
            state: State parameter (typically user_id)
            redirect_uri: Redirect URI used in the OAuth flow

        Returns:
            Tuple of (success: bool, message: str)
        """
        pass


class GoogleDriveProvider(OAuthProvider):
    """Google Drive OAuth provider implementation."""

    def __init__(self, token_storage: TokenStorage):
        """Initialize Google Drive OAuth provider.

        Args:
            token_storage: TokenStorage instance for database-backed credentials
        """
        self.token_storage = token_storage
        self._client_id = os.environ.get("GDRIVE_CLIENT_ID")
        self._client_secret = os.environ.get("GDRIVE_CLIENT_SECRET")
        self._scopes = [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/documents.readonly",
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/presentations.readonly",
        ]

    def get_provider_name(self) -> str:
        """Get the provider name."""
        return "google"

    def is_configured(self) -> bool:
        """Check if Google Drive OAuth credentials are configured."""
        return bool(self._client_id and self._client_secret)

    def exchange_code_for_token(self, code: str, state: str, redirect_uri: str) -> tuple[bool, str]:
        """Exchange authorization code for Google Drive access token.

        Args:
            code: OAuth authorization code
            state: Signed JWT state token containing user_id
            redirect_uri: Redirect URI used in the OAuth flow

        Returns:
            Tuple of (success: bool, message: str)
        """
        # Validate state token to prevent CSRF attacks
        try:
            user_id = validate_state_token(state)
        except StateTokenExpiredError as e:
            logger.warning(f"Google Drive OAuth state token expired: {e}")
            return False, "Authorization expired. Please try again."
        except StateTokenInvalidError as e:
            logger.error(f"Google Drive OAuth invalid state token (possible CSRF attack): {e}")
            return False, "Invalid authorization request. Please try again."
        except StateTokenError as e:
            logger.error(f"Google Drive OAuth state token error: {e}")
            return False, "Authorization failed. Please try again."

        try:
            logger.info(f"Exchanging Google Drive authorization code for user {user_id}")

            # Create OAuth flow
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [redirect_uri],
                    }
                },
                scopes=self._scopes,
                redirect_uri=redirect_uri,
            )

            # Exchange code for token (with timeout to prevent DoS)
            # Note: Flow.fetch_token internally uses requests with timeout
            flow.fetch_token(code=code, timeout=10)

            # Get credentials
            credentials = flow.credentials

            if not credentials:
                logger.error(f"Failed to get credentials for user {user_id}")
                return False, "Failed to complete authorization"

            logger.info(f"✅ Successfully exchanged code for Google Drive token (user: {user_id})")
            logger.info(f"📊 Token details for user {user_id}:")
            logger.info("  - Token type: Bearer")
            logger.info(f"  - Expires at: {credentials.expiry.strftime('%Y-%m-%d %H:%M:%S UTC') if credentials.expiry else 'N/A'}")
            logger.info(f"  - Has refresh token: {bool(credentials.refresh_token)}")
            logger.info(f"  - Scopes: {', '.join(credentials.scopes)}")

            # Store credentials in database
            logger.info(f"💾 Storing Google Drive token in database for user {user_id}")
            logger.debug(f"📂 Database path: {self.token_storage.db_path}")
            success = self.token_storage.upsert_token(
                "gdrive",
                user_id=user_id,
                credentials=credentials,
            )

            if not success:
                logger.error(f"Failed to store Google Drive token for user {user_id}")
                return False, "Failed to save credentials"

            logger.info(f"✅ Stored Google Drive token in database for user {user_id}")
            logger.debug(f"📂 Token stored at: {self.token_storage.db_path}")

            return True, f"Successfully authenticated Google Drive for user {user_id}"

        except GoogleAuthError as e:
            logger.error(f"Google Drive OAuth authentication error for user {user_id}: {e}")
            return False, "Google authentication failed. Please try again."
        except requests.exceptions.Timeout as e:
            logger.error(f"Google Drive OAuth timeout for user {user_id}: {e}")
            return False, "Authorization request timed out. Please try again."
        except requests.exceptions.RequestException as e:
            logger.error(f"Google Drive OAuth network error for user {user_id}: {e}")
            return False, "Network error during authorization. Please try again."
        except Exception as e:
            logger.error(f"Google Drive OAuth callback failed for user {user_id}: {e}")
            return False, "Authorization failed. Please try again."


class GitHubProvider(OAuthProvider):
    """GitHub OAuth provider implementation."""

    def __init__(self, token_storage: TokenStorage):
        """Initialize GitHub OAuth provider.

        Args:
            token_storage: TokenStorage instance for database-backed credentials
        """
        self.token_storage = token_storage
        self._client_id = os.environ.get("GITHUB_CLIENT_ID")
        self._client_secret = os.environ.get("GITHUB_CLIENT_SECRET")

    def get_provider_name(self) -> str:
        """Get the provider name."""
        return "github"

    def is_configured(self) -> bool:
        """Check if GitHub OAuth credentials are configured."""
        return bool(self._client_id and self._client_secret)

    def exchange_code_for_token(self, code: str, state: str, redirect_uri: str) -> tuple[bool, str]:
        """Exchange authorization code for GitHub access token.

        Args:
            code: OAuth authorization code
            state: Signed JWT state token containing user_id
            redirect_uri: Redirect URI used in the OAuth flow

        Returns:
            Tuple of (success: bool, message: str)
        """
        # Validate state token to prevent CSRF attacks
        try:
            user_id = validate_state_token(state)
        except StateTokenExpiredError as e:
            logger.warning(f"GitHub OAuth state token expired: {e}")
            return False, "Authorization expired. Please try again."
        except StateTokenInvalidError as e:
            logger.error(f"GitHub OAuth invalid state token (possible CSRF attack): {e}")
            return False, "Invalid authorization request. Please try again."
        except StateTokenError as e:
            logger.error(f"GitHub OAuth state token error: {e}")
            return False, "Authorization failed. Please try again."

        try:
            logger.info(f"Exchanging GitHub authorization code for user {user_id}")

            # Exchange code for token (with timeout to prevent DoS)
            token_response = requests.post(
                "https://github.com/login/oauth/access_token",
                headers={"Accept": "application/json"},
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                timeout=10,  # 10 second timeout to prevent DoS
            )

            token_response.raise_for_status()
            token_data = token_response.json()

            if "error" in token_data:
                logger.error(f"GitHub OAuth error for user {user_id}: {token_data.get('error_description')}")
                return False, "GitHub authorization failed. Please try again."

            access_token = token_data.get("access_token")
            if not access_token:
                logger.error(f"No access token in GitHub response for user {user_id}")
                return False, "Failed to receive access token from GitHub"

            # Get user info (with timeout to prevent DoS)
            user_response = requests.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=10,  # 10 second timeout to prevent DoS
            )
            user_response.raise_for_status()
            user_data = user_response.json()

            username = user_data.get("login")

            logger.info(f"✅ Successfully exchanged code for GitHub token (user: {user_id})")
            logger.info(f"📊 Token details for user {user_id}:")
            logger.info(f"  - GitHub username: {username}")
            logger.info(f"  - Token type: {token_data.get('token_type', 'bearer')}")
            logger.info(f"  - Scopes: {token_data.get('scope', 'default')}")

            # Store token in database
            logger.info(f"💾 Storing GitHub token in database for user {user_id}")
            success = self.token_storage.upsert_token(
                "github",
                user_id=user_id,
                token=access_token,
                server_url="https://api.github.com",
                username=username,
            )

            if not success:
                logger.error(f"Failed to store GitHub token for user {user_id}")
                return False, "Failed to save credentials"

            logger.info(f"✅ Stored GitHub token in database for user {user_id}")

            return True, f"Successfully authenticated GitHub for user {user_id} ({username})"

        except requests.exceptions.Timeout as e:
            logger.error(f"GitHub OAuth timeout for user {user_id}: {e}")
            return False, "Authorization request timed out. Please try again."
        except requests.exceptions.HTTPError as e:
            logger.error(f"GitHub OAuth HTTP error for user {user_id}: {e}")
            return False, "GitHub authorization failed. Please try again."
        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub OAuth network error for user {user_id}: {e}")
            return False, "Network error during authorization. Please try again."
        except Exception as e:
            logger.error(f"GitHub OAuth callback failed for user {user_id}: {e}")
            return False, "Authorization failed. Please try again."


class ProviderRegistry:
    """Registry for OAuth providers."""

    def __init__(self, token_storage: TokenStorage):
        """Initialize provider registry.

        Args:
            token_storage: TokenStorage instance shared across all providers
        """
        self.token_storage = token_storage
        self._providers: dict[str, OAuthProvider] = {}

        # Register built-in providers
        self._register_provider(GoogleDriveProvider(token_storage))
        self._register_provider(GitHubProvider(token_storage))

    def _register_provider(self, provider: OAuthProvider) -> None:
        """Register an OAuth provider.

        Args:
            provider: OAuthProvider instance
        """
        provider_name = provider.get_provider_name()
        self._providers[provider_name] = provider
        logger.debug(f"Registered OAuth provider: {provider_name}")

    def get_provider(self, provider_name: str) -> OAuthProvider | None:
        """Get OAuth provider by name.

        Args:
            provider_name: Provider name (e.g., 'google', 'github')

        Returns:
            OAuthProvider instance or None if not found
        """
        return self._providers.get(provider_name)

    def get_all_providers(self) -> dict[str, OAuthProvider]:
        """Get all registered providers.

        Returns:
            Dictionary of provider_name -> OAuthProvider
        """
        return self._providers.copy()

    def get_configured_providers(self) -> list[str]:
        """Get list of configured provider names.

        Returns:
            List of provider names that have OAuth credentials configured
        """
        return [name for name, provider in self._providers.items() if provider.is_configured()]
