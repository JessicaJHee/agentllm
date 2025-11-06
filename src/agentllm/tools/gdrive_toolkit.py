"""Google Drive toolkit for retrieving document content.

Returns document content as strings instead of saving to disk.
"""

import json
from typing import Any

from agno.tools import Toolkit
from google.oauth2.credentials import Credentials
from loguru import logger

from .gdrive_utils import GoogleDriveExporter


class GoogleDriveTools(Toolkit):
    """Toolkit for retrieving content from Google Drive documents.

    Returns document content as strings. Documents are returned as markdown,
    spreadsheets as CSV, and presentations as plain text.
    """

    def __init__(
        self,
        credentials: Credentials,
        **kwargs,
    ):
        """Initialize Google Drive toolkit with OAuth credentials.

        Args:
            credentials: Google OAuth2 credentials
            **kwargs: Additional arguments passed to parent Toolkit
        """
        # Create exporter with pre-authenticated credentials (no file storage needed)
        self.exporter = GoogleDriveExporter(credentials=credentials)

        tools: list[Any] = [
            self.get_document_content,
            self.get_user_info,
        ]

        super().__init__(name="gdrive_tools", tools=tools, **kwargs)

    def get_document_content(self, url_or_id: str) -> str:
        """Get content from a Google Drive document.

        Automatically handles different document types:
        - Google Docs: Returns as markdown
        - Google Sheets: Returns as CSV
        - Google Slides: Returns as plain text

        Args:
            url_or_id: Google Drive URL or document ID

        Returns:
            Document content as string, or error message if retrieval fails
        """
        try:
            logger.info(f"Retrieving Google Drive document content: {url_or_id}")

            # Get document content with automatic format detection
            content = self.exporter.get_document_content_as_string(url_or_id, format_key=None)

            if content is None:
                return f"Failed to retrieve document content: {url_or_id}"

            logger.info(f"Successfully retrieved document content ({len(content)} characters)")
            return content

        except Exception as e:
            error_msg = f"Error retrieving document {url_or_id}: {e}"
            logger.error(error_msg)
            return error_msg

    def get_user_info(self) -> str:
        """Get information about the currently authenticated Google user.

        Returns:
            User information or error message
        """
        try:
            user_info = self.exporter.get_authenticated_user_info()

            if not user_info:
                return "No user information available. Authentication may be required."

            result = {
                "authenticated_user": {
                    "display_name": user_info.get("displayName", "Unknown"),
                    "email": user_info.get("emailAddress", "Unknown"),
                    "photo_link": user_info.get("photoLink", ""),
                }
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            error_msg = f"Error getting user info: {e}"
            logger.error(error_msg)
            return error_msg
