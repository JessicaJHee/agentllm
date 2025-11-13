"""Red Hat AI (RHAI) Toolkit."""

import os
from typing import Any

from agno.tools import Toolkit
from google.oauth2.credentials import Credentials
from loguru import logger
from pydantic import BaseModel, Field

from agentllm.tools.gdrive_utils import GoogleDriveExporter


class RHAIRelease(BaseModel):
    """Data model for a Red Hat AI release."""

    release: str = Field(..., description="Name of the release")
    details: str = Field(..., description="Details about the release")
    planned_release_date: str = Field(..., description="Planned release date")


class CantGetReleasesError(Exception):
    """Exception raised when releases cannot be retrieved."""


class CantParseReleasesError(Exception):
    """Exception raised when releases cannot be parsed."""


class RHAITools(Toolkit):
    """Toolkit for Red Hat AI (RHAI)."""

    def __init__(
        self,
        credentials: Credentials,
        **kwargs,
    ):
        """Initialize toolkit with OAuth credentials.

        Args:
            credentials: Google OAuth2 credentials
            **kwargs: Additional arguments passed to parent Toolkit
        """
        # Create exporter with pre-authenticated credentials (no file storage needed)
        self.exporter = GoogleDriveExporter(credentials=credentials)

        tools: list[Any] = [
            self.get_releases,
        ]

        super().__init__(name="rhai_tools", tools=tools, **kwargs)

    def get_releases(self) -> list[RHAIRelease]:
        """Get list of Red Hat AI releases from a Google Sheets document.

        The document should contain tab-separated values with columns:
        Release, Details, Planned Release Date

        Returns:
            List of RHAIRelease objects

        Raises:
            ValueError: If AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET is not set
            CantParseReleasesError: If document cannot be retrieved or parsed
        """
        # Get document URL from environment
        doc_url = os.getenv("AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET")
        if not doc_url:
            raise ValueError("Environment variable AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET must be set")

        try:
            # Fetch document content
            logger.info(f"Fetching RHAI releases from: {doc_url}")
            content = self.exporter.get_document_content_as_string(doc_url, format_key=None)

            if content is None:
                raise CantGetReleasesError("Document content is None")

            # Parse tab-separated values
            releases: list[RHAIRelease] = []
            lines = content.strip().split("\n")

            # Skip header line (first line)
            for i, line in enumerate(lines[1:], start=2):
                parts = line.split("\t")

                # Skip lines with insufficient columns
                if len(parts) < 3:
                    logger.warning(f"Skipping line {i}: insufficient columns (expected 3, got {len(parts)})")
                    continue

                # Extract fields (take first 3 columns, ignore extras)
                release = RHAIRelease(
                    release=parts[0],
                    details=parts[1],
                    planned_release_date=parts[2],
                )
                releases.append(release)

            logger.info(f"Successfully parsed {len(releases)} releases")
            return releases

        except CantGetReleasesError as e:
            # Re-raise as CantParseReleasesError for consistency with tests
            raise CantParseReleasesError("Failed to retrieve releases from document") from e
        except Exception as e:
            logger.error(f"Error fetching/parsing releases: {e}")
            raise CantParseReleasesError(f"Failed to parse releases: {e}") from e
