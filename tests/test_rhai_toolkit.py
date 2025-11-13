"""
Tests for the RHAI Toolkit.

This test suite covers:
- Toolkit instantiation with credentials
- get_releases() method functionality
- Error handling for missing environment variables
- Error handling for document retrieval failures
- Data parsing from tab-separated values
- Edge cases (empty documents, malformed data, etc.)
"""

import os
from unittest.mock import MagicMock, Mock, patch

import pytest
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials

from agentllm.tools import (
    CantParseReleasesError,
    RHAIRelease,
    RHAITools,
)

# Load .env file for tests
load_dotenv()


# Test fixtures
@pytest.fixture
def mock_credentials() -> Credentials:
    """Provide mock Google OAuth2 credentials."""
    creds = Mock(spec=Credentials)
    creds.token = "mock_access_token"
    creds.refresh_token = "mock_refresh_token"
    creds.client_id = "mock_client_id"
    creds.client_secret = "mock_client_secret"
    creds.token_uri = "https://oauth2.googleapis.com/token"
    return creds


@pytest.fixture
def sample_release_data() -> str:
    """Provide sample release data in tab-separated format."""
    return """Release\tDetails\tPlanned Release Date
1.5.0\tGA release with new features\t2025-02-15
1.5.1\tBugfix release\t2025-03-01
1.6.0\tMajor feature release\t2025-04-30"""


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


class TestRHAIToolsInstantiation:
    """Tests for RHAITools instantiation and initialization."""

    def test_create_toolkit(self, mock_credentials: Credentials):
        """Test that RHAITools can be instantiated with credentials."""
        toolkit = RHAITools(credentials=mock_credentials)
        assert toolkit is not None
        assert hasattr(toolkit, "exporter")
        assert hasattr(toolkit, "get_releases")

    def test_toolkit_has_correct_name(self, mock_credentials: Credentials):
        """Test that toolkit has the correct name."""
        toolkit = RHAITools(credentials=mock_credentials)
        assert toolkit.name == "rhai_tools"

    def test_toolkit_registers_get_releases_tool(self, mock_credentials: Credentials):
        """Test that get_releases is registered as a tool."""
        toolkit = RHAITools(credentials=mock_credentials)
        # The tools list should contain get_releases
        assert len(toolkit.tools) >= 1
        # Check if get_releases is in the tools
        tool_names = [getattr(tool, "__name__", str(tool)) for tool in toolkit.tools]
        assert "get_releases" in tool_names


class TestGetReleasesSuccess:
    """Tests for successful get_releases() scenarios."""

    @patch("agentllm.tools.rhai_toolkit.GoogleDriveExporter")
    def test_get_releases_returns_list(
        self,
        mock_exporter_class,
        mock_credentials: Credentials,
        sample_release_data: str,
        env_var_set,
    ):
        """Test that get_releases returns a list of RHAIRelease objects."""
        # Setup mock
        mock_exporter = MagicMock()
        mock_exporter.get_document_content_as_string.return_value = sample_release_data
        mock_exporter_class.return_value = mock_exporter

        toolkit = RHAITools(credentials=mock_credentials)
        releases = toolkit.get_releases()

        assert isinstance(releases, list)
        assert len(releases) == 3
        assert all(isinstance(r, RHAIRelease) for r in releases)

    @patch("agentllm.tools.rhai_toolkit.GoogleDriveExporter")
    def test_get_releases_parses_data_correctly(
        self,
        mock_exporter_class,
        mock_credentials: Credentials,
        sample_release_data: str,
        env_var_set,
    ):
        """Test that get_releases correctly parses release data."""
        # Setup mock
        mock_exporter = MagicMock()
        mock_exporter.get_document_content_as_string.return_value = sample_release_data
        mock_exporter_class.return_value = mock_exporter

        toolkit = RHAITools(credentials=mock_credentials)
        releases = toolkit.get_releases()

        # Check first release
        assert releases[0].release == "1.5.0"
        assert releases[0].details == "GA release with new features"
        assert releases[0].planned_release_date == "2025-02-15"

        # Check second release
        assert releases[1].release == "1.5.1"
        assert releases[1].details == "Bugfix release"
        assert releases[1].planned_release_date == "2025-03-01"

        # Check third release
        assert releases[2].release == "1.6.0"
        assert releases[2].details == "Major feature release"
        assert releases[2].planned_release_date == "2025-04-30"

    @patch("agentllm.tools.rhai_toolkit.GoogleDriveExporter")
    def test_get_releases_skips_header_line(
        self,
        mock_exporter_class,
        mock_credentials: Credentials,
        sample_release_data: str,
        env_var_set,
    ):
        """Test that get_releases skips the header line."""
        # Setup mock
        mock_exporter = MagicMock()
        mock_exporter.get_document_content_as_string.return_value = sample_release_data
        mock_exporter_class.return_value = mock_exporter

        toolkit = RHAITools(credentials=mock_credentials)
        releases = toolkit.get_releases()

        # Should not include "Release" as a release name (header)
        release_names = [r.release for r in releases]
        assert "Release" not in release_names

    @patch("agentllm.tools.rhai_toolkit.GoogleDriveExporter")
    def test_get_releases_calls_exporter_with_correct_url(
        self,
        mock_exporter_class,
        mock_credentials: Credentials,
        sample_release_data: str,
        env_var_set,
    ):
        """Test that get_releases calls the exporter with the correct document URL."""
        # Setup mock
        mock_exporter = MagicMock()
        mock_exporter.get_document_content_as_string.return_value = sample_release_data
        mock_exporter_class.return_value = mock_exporter

        toolkit = RHAITools(credentials=mock_credentials)
        toolkit.get_releases()

        # Verify the exporter was called with the correct URL
        mock_exporter.get_document_content_as_string.assert_called_once_with(
            "https://docs.google.com/document/d/test_doc_id/edit", format_key=None
        )


class TestGetReleasesErrorHandling:
    """Tests for error handling in get_releases()."""

    def test_get_releases_raises_value_error_if_env_var_not_set(self, mock_credentials: Credentials):
        """Test that get_releases raises ValueError if environment variable is not set."""
        # Ensure env var is not set
        original_value = os.environ.pop("AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET", None)

        try:
            toolkit = RHAITools(credentials=mock_credentials)
            with pytest.raises(ValueError) as exc_info:
                toolkit.get_releases()

            assert "AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET" in str(exc_info.value)
        finally:
            # Restore original value
            if original_value is not None:
                os.environ["AGENTLLM_RHAI_ROADMAP_PUBLISHER_RELEASE_SHEET"] = original_value

    @patch("agentllm.tools.rhai_toolkit.GoogleDriveExporter")
    def test_get_releases_raises_error_if_document_content_is_none(self, mock_exporter_class, mock_credentials: Credentials, env_var_set):
        """Test that get_releases raises CantParseReleasesError if document content is None.

        Note: CantGetReleasesError is caught by the outer exception handler and re-raised
        as CantParseReleasesError. This is the current behavior.
        """
        # Setup mock to return None
        mock_exporter = MagicMock()
        mock_exporter.get_document_content_as_string.return_value = None
        mock_exporter_class.return_value = mock_exporter

        toolkit = RHAITools(credentials=mock_credentials)
        with pytest.raises(CantParseReleasesError):
            toolkit.get_releases()

    @patch("agentllm.tools.rhai_toolkit.GoogleDriveExporter")
    def test_get_releases_raises_parse_error_on_exporter_exception(self, mock_exporter_class, mock_credentials: Credentials, env_var_set):
        """Test that get_releases raises CantParseReleasesError if exporter throws exception."""
        # Setup mock to raise exception
        mock_exporter = MagicMock()
        mock_exporter.get_document_content_as_string.side_effect = Exception("Network error")
        mock_exporter_class.return_value = mock_exporter

        toolkit = RHAITools(credentials=mock_credentials)
        with pytest.raises(CantParseReleasesError):
            toolkit.get_releases()


class TestGetReleasesEdgeCases:
    """Tests for edge cases in get_releases()."""

    @patch("agentllm.tools.rhai_toolkit.GoogleDriveExporter")
    def test_get_releases_handles_empty_document(self, mock_exporter_class, mock_credentials: Credentials, env_var_set):
        """Test that get_releases handles an empty document (only header)."""
        # Setup mock with only header
        mock_exporter = MagicMock()
        mock_exporter.get_document_content_as_string.return_value = "Release\tDetails\tPlanned Release Date"
        mock_exporter_class.return_value = mock_exporter

        toolkit = RHAITools(credentials=mock_credentials)
        releases = toolkit.get_releases()

        assert isinstance(releases, list)
        assert len(releases) == 0

    @patch("agentllm.tools.rhai_toolkit.GoogleDriveExporter")
    def test_get_releases_skips_malformed_lines(self, mock_exporter_class, mock_credentials: Credentials, env_var_set):
        """Test that get_releases skips lines with insufficient columns."""
        # Setup mock with some malformed lines
        malformed_data = """Release\tDetails\tPlanned Release Date
1.5.0\tGA release with new features\t2025-02-15
1.5.1\tIncomplete line
1.6.0\tMajor feature release\t2025-04-30"""

        mock_exporter = MagicMock()
        mock_exporter.get_document_content_as_string.return_value = malformed_data
        mock_exporter_class.return_value = mock_exporter

        toolkit = RHAITools(credentials=mock_credentials)
        releases = toolkit.get_releases()

        # Should only parse valid lines (2 out of 3)
        assert len(releases) == 2
        assert releases[0].release == "1.5.0"
        assert releases[1].release == "1.6.0"

    @patch("agentllm.tools.rhai_toolkit.GoogleDriveExporter")
    def test_get_releases_handles_extra_columns(self, mock_exporter_class, mock_credentials: Credentials, env_var_set):
        """Test that get_releases handles lines with extra columns."""
        # Setup mock with extra columns
        extra_columns_data = """Release\tDetails\tPlanned Release Date
1.5.0\tGA release with new features\t2025-02-15\tExtra\tColumn"""

        mock_exporter = MagicMock()
        mock_exporter.get_document_content_as_string.return_value = extra_columns_data
        mock_exporter_class.return_value = mock_exporter

        toolkit = RHAITools(credentials=mock_credentials)
        releases = toolkit.get_releases()

        # Should parse successfully, ignoring extra columns
        assert len(releases) == 1
        assert releases[0].release == "1.5.0"
        assert releases[0].details == "GA release with new features"
        assert releases[0].planned_release_date == "2025-02-15"

    @patch("agentllm.tools.rhai_toolkit.GoogleDriveExporter")
    def test_get_releases_handles_whitespace_in_data(self, mock_exporter_class, mock_credentials: Credentials, env_var_set):
        """Test that get_releases preserves whitespace in field values."""
        # Setup mock with whitespace
        whitespace_data = """Release\tDetails\tPlanned Release Date
1.5.0\t  GA release with new features  \t2025-02-15"""

        mock_exporter = MagicMock()
        mock_exporter.get_document_content_as_string.return_value = whitespace_data
        mock_exporter_class.return_value = mock_exporter

        toolkit = RHAITools(credentials=mock_credentials)
        releases = toolkit.get_releases()

        # Whitespace should be preserved (no trimming)
        assert len(releases) == 1
        assert releases[0].details == "  GA release with new features  "

    @patch("agentllm.tools.rhai_toolkit.GoogleDriveExporter")
    def test_get_releases_handles_empty_fields(self, mock_exporter_class, mock_credentials: Credentials, env_var_set):
        """Test that get_releases handles empty field values."""
        # Setup mock with empty fields
        empty_fields_data = """Release\tDetails\tPlanned Release Date
1.5.0\t\t2025-02-15"""

        mock_exporter = MagicMock()
        mock_exporter.get_document_content_as_string.return_value = empty_fields_data
        mock_exporter_class.return_value = mock_exporter

        toolkit = RHAITools(credentials=mock_credentials)
        releases = toolkit.get_releases()

        # Should parse successfully with empty details field
        assert len(releases) == 1
        assert releases[0].release == "1.5.0"
        assert releases[0].details == ""
        assert releases[0].planned_release_date == "2025-02-15"


class TestRHAIReleaseModel:
    """Tests for the RHAIRelease data model."""

    def test_rhai_release_creation(self):
        """Test that RHAIRelease can be created with valid data."""
        release = RHAIRelease(
            release="1.5.0",
            details="GA release with new features",
            planned_release_date="2025-02-15",
        )
        assert release.release == "1.5.0"
        assert release.details == "GA release with new features"
        assert release.planned_release_date == "2025-02-15"

    def test_rhai_release_requires_all_fields(self):
        """Test that RHAIRelease requires all fields."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            RHAIRelease(release="1.5.0", details="GA release")  # Missing planned_release_date

    def test_rhai_release_accepts_empty_strings(self):
        """Test that RHAIRelease accepts empty strings for fields."""
        release = RHAIRelease(release="", details="", planned_release_date="")
        assert release.release == ""
        assert release.details == ""
        assert release.planned_release_date == ""
