"""Red Hat AI toolkit functions."""

import logging
import os
from typing import TYPE_CHECKING, Any

from agentllm.agents.toolkit_configs.base import BaseToolkitConfig
from agentllm.tools.rhai_toolkit import RHAITools

if TYPE_CHECKING:
    from agentllm.agents.toolkit_configs.gdrive_config import GoogleDriveConfig
    from agentllm.db.token_storage import TokenStorage


logger = logging.getLogger(__name__)


class RHAIToolkitConfig(BaseToolkitConfig):
    """A toolkit for Red Hat AI specific functions, for example to get a list of releases."""

    def __init__(
        self,
        gdrive_config: "GoogleDriveConfig",
        token_storage: "TokenStorage | None" = None,
    ):
        """Initialize RHAI toolkit configuration.

        Args:
            gdrive_config: Google Drive configuration with OAuth credentials.
            token_storage: Optional shared token storage (for consistency with base class)
        """
        super().__init__(token_storage)
        self._gdrive_config = gdrive_config
        self._doc_url = os.getenv("AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET")
        self._toolkits: dict[str, RHAITools] = {}

        if self._doc_url:
            logger.info("RHAI toolkit configured with release sheet: %s", self._doc_url)
        else:
            logger.debug("RHAI toolkit not configured (AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET not set)")

    def check_authorization_request(self, message: str, user_id: str) -> str | None:  # noqa: ARG002
        """Check if message requests this toolkit and handle authorization.

        RHAI Toolkit doesn't require separate authorization.
        It piggybacks on GoogleDriveConfig authorization.

        Args:
            message: User message
            user_id: User identifier

        Returns:
            None (no authorization needed)
        """
        return None

    def extract_and_store_config(self, message: str, user_id: str) -> str | None:  # noqa: ARG002
        """Try to extract configuration from user message.

        RHAI Toolkit has no extractable configuration from messages.
        Configuration comes from environment variables and GDrive credentials.

        Args:
            message: User message
            user_id: User identifier

        Returns:
            None (no configuration to extract)
        """
        return None

    def get_config_prompt(self, user_id: str) -> str | None:  # noqa: ARG002
        """Get prompt for missing configuration.

        RHAI Toolkit is silent about its configuration needs.
        If GDrive is not configured, GoogleDriveConfig will handle prompting.

        Args:
            user_id: User identifier

        Returns:
            None (no prompt needed)
        """
        return None

    def get_toolkit(self, user_id: str) -> Any | None:  # noqa: PLR0911
        """Get RHAI toolkit instance for user.

        Creates RHAITools with Google Drive credentials if:
        - User has configured Google Drive
        - AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET is set

        Args:
            user_id: User identifier

        Returns:
            RHAITools instance if fully configured, None otherwise
        """
        # Check if already instantiated for this user
        if user_id in self._toolkits:
            return self._toolkits[user_id]

        # Check if fully configured
        if not self.is_configured(user_id):
            return None

        # Get Google Drive credentials from gdrive_config
        gdrive_toolkit = self._gdrive_config.get_toolkit(user_id)
        if not gdrive_toolkit:
            logger.warning(
                "RHAI toolkit: Google Drive toolkit not available for user %s",
                user_id,
            )
            return None

        # Get credentials from GDrive config's internal method
        # Note: We access the private method since GoogleDriveConfig doesn't
        # expose credentials publicly
        try:
            creds = self._gdrive_config._get_gdrive_credentials(user_id)  # noqa: SLF001
            if not creds:
                logger.warning(
                    "RHAI toolkit: Could not retrieve Google Drive credentials for user %s",
                    user_id,
                )
                return None
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to retrieve Google Drive credentials for user %s",
                user_id,
            )
            return None

        # Instantiate RHAITools with credentials
        try:
            toolkit = RHAITools(credentials=creds)
            self._toolkits[user_id] = toolkit
            logger.info("Created RHAI toolkit for user %s", user_id)
            return toolkit
        except Exception:  # noqa: BLE001
            logger.exception("Failed to create RHAI toolkit for user %s", user_id)
            return None

    def is_configured(self, user_id: str) -> bool:
        """Check if RHAI Toolkit is fully configured for a user.

        Returns True if:
        - Environment variable AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET is set, AND
        - Google Drive is configured for this user

        Args:
            user_id: User identifier

        Returns:
            True if configured, False otherwise
        """
        # If no document URL, extension is not configured
        if not self._doc_url:
            return False

        # Document URL is set, check if GDrive is configured
        return self._gdrive_config.is_configured(user_id)

    def is_required(self) -> bool:
        """Check if this toolkit configuration is required.

        Returns:
            True - RHAI Toolkit is required when configured
        """
        return True

    def get_agent_instructions(self, user_id: str) -> list[str]:
        """Provide instructions for using RHAI release data.

        Args:
            user_id: User identifier

        Returns:
            List of instruction strings if configured, empty list otherwise
        """
        if not self.is_configured(user_id):
            return []

        instructions = [
            "",
            "## RHAI Release Information",
            "",
            "You have access to the `get_releases()` tool which provides official Red Hat AI release data:",
            "- Release names/versions (e.g., 'RHOAI 2.15', 'RHOAI 2.16')",
            "- Release details/descriptions",
            "- Planned release dates",
            "",
            "**When to use this data:**",
            "- Include release information in the '## Releases' section of roadmaps",
            "- Cross-reference JIRA 'Target Version' fields with planned release dates",
            "- Validate feature timelines against release schedules",
            "- Provide context on which features will ship in which releases",
            "",
            "**How to use:**",
            "1. Call `get_releases()` to fetch current release data (no parameters needed)",
            "2. Match JIRA 'Target Version' fields to release names from the data",
            "3. Include relevant releases in the '## Releases' section of your roadmap",
            "4. Use planned release dates to validate feature timeline placement",
            "",
            "**Example workflow:**",
            "1. Search JIRA for features with specific labels",
            "2. Call `get_releases()` to get release schedule",
            "3. Cross-reference feature target versions with release dates",
            "4. Organize features by quarter based on release dates",
            "5. Include release schedule in roadmap output",
        ]

        return instructions
