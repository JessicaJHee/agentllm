"""
Tests for the SprintReviewer agent.

This test suite covers:
- Agent instantiation and configuration
- Jira toolkit methods (search_issues, get_issue, get_sprint_metrics, extract_sprint_info)
"""

import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from agno.db.sqlite import SqliteDb
from dotenv import load_dotenv

from agentllm.agents.sprint_reviewer import SprintReviewer
from agentllm.db import TokenStorage

# Load .env file for tests
load_dotenv()

# Map GEMINI_API_KEY to GOOGLE_API_KEY if needed
if "GOOGLE_API_KEY" not in os.environ and "GEMINI_API_KEY" in os.environ:
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]


# Test fixtures
@pytest.fixture
def shared_db() -> SqliteDb:
    """Provide a shared test database."""
    db_path = Path("tmp/test_sprint_reviewer.db")
    db_path.parent.mkdir(exist_ok=True)
    db = SqliteDb(db_file=str(db_path))
    yield db
    # Cleanup after tests
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def token_storage(shared_db: SqliteDb) -> TokenStorage:
    """Provide a token storage instance."""
    return TokenStorage(agno_db=shared_db)


@pytest.fixture
def mock_jira_client():
    """Provide a mocked JIRA client."""
    with patch("agentllm.tools.jira_toolkit.JIRA") as mock_jira_class:
        mock_jira = MagicMock()
        mock_jira_class.return_value = mock_jira
        yield mock_jira


class TestSprintReviewerBasics:
    """Basic tests for SprintReviewer instantiation and parameters."""

    def test_create_agent(self, shared_db, token_storage):
        """Test that SprintReviewer can be instantiated."""
        agent = SprintReviewer(shared_db=shared_db, token_storage=token_storage, user_id="test-user")
        assert agent is not None
        assert agent._configurator is not None

    def test_create_agent_with_params(self, shared_db, token_storage):
        """Test that SprintReviewer accepts model parameters."""
        agent = SprintReviewer(
            shared_db=shared_db,
            token_storage=token_storage,
            user_id="test-user",
            temperature=0.5,
            max_tokens=100,
        )
        assert agent is not None
        assert agent._configurator._temperature == 0.5
        assert agent._configurator._max_tokens == 100


class TestSprintReviewerJiraToolkit:
    """Tests for JIRA toolkit methods used by SprintReviewer."""

    def _create_mock_issue(
        self,
        key="PROJ-123",
        summary="Test issue",
        status="Closed",
        priority="Major",
        issue_type="Story",
        epic_link=None,
        sprint_data=None,
    ):
        """Create a mock JIRA issue for testing."""
        from jira import Issue
        
        mock_issue = MagicMock(spec=Issue)
        mock_issue.key = key
        mock_issue.fields = MagicMock()
        mock_issue.fields.summary = summary        
        mock_issue.fields.status = MagicMock()
        mock_issue.fields.status.name = status
        mock_issue.fields.priority = MagicMock()
        mock_issue.fields.priority.name = priority
        mock_issue.fields.issuetype = MagicMock()
        mock_issue.fields.issuetype.name = issue_type        
        mock_issue.fields.customfield_12311140 = epic_link
        mock_issue.fields.customfield_12310940 = sprint_data
        
        return mock_issue

    def test_search_issues_returns_formatted_issues(self, mock_jira_client):
        """Test that search_issues returns properly formatted issues."""
        from agentllm.tools.jira_toolkit import JiraTools
        
        # Wrapper to handle MagicMock serialization
        _dumps = json.dumps
        def dumps_wrapper(*args, **kwargs):
            return _dumps(*args, **(kwargs | {"default": lambda obj: "MagicMock"}))

        mock_issue1 = self._create_mock_issue(
            key="PROJ-123",
            summary="Create frontend plugin for ServiceNow",
            status="Closed",
            priority="Major",
            issue_type="Story",
            epic_link="PROJ-100",
        )
        mock_issue2 = self._create_mock_issue(
            key="PROJ-124",
            summary="Enhance logging",
            status="In progress",
            priority="Normal",
            issue_type="Task",
        )
        
        mock_jira_client.search_issues.return_value = [mock_issue1, mock_issue2]
        
        with patch("agentllm.tools.jira_toolkit.json.dumps", MagicMock(wraps=dumps_wrapper)):
            toolkit = JiraTools(
                token="test_token",
                server_url="https://mock-jira-url.com",
                search_issues=True,
            )
            result_str = toolkit.search_issues("project = TEST_PROJECT")
            result = json.loads(result_str)
            
            assert isinstance(result, list), "Result should be a list"
            assert len(result) == 2, f"Expected 2 issues, got {len(result)}"
            
            issue1 = result[0]
            assert issue1.get("key") == "PROJ-123"
            assert issue1.get("summary") == "Create frontend plugin for ServiceNow"
            assert issue1.get("custom_fields").get("epic_link") == "PROJ-100"
            issue2 = result[1]
            assert issue2.get("key") == "PROJ-124"
            assert issue2.get("custom_fields").get("epic_link") is None

    def test_get_sprint_metrics_returns_correct_values(self, mock_jira_client):
        """Test that get_sprint_metrics returns correct metric values."""
        from agentllm.tools.jira_toolkit import JiraTools
        
        mock_jira_client.search_issues.side_effect = [
            SimpleNamespace(total=25),  # total_planned query
            SimpleNamespace(total=18),  # total_closed query
            SimpleNamespace(total=15),  # stories_tasks query
            SimpleNamespace(total=3),   # bugs query
        ]
        
        toolkit = JiraTools(
            token="test_token",
            server_url="https://mock-jira-url.com",
            get_sprint_metrics=True,
        )

        result_str = toolkit.get_sprint_metrics("75290")
        result = json.loads(result_str)
        
        assert result["sprint_id"] == "75290"
        assert result["total_planned"] == 25
        assert result["total_closed"] == 18
        assert result["stories_tasks_closed"] == 15
        assert result["bugs_closed"] == 3

    def test_extract_sprint_info_returns_sprint_details(self, mock_jira_client):
        """Test that extract_sprint_info returns sprint ID and name."""
        from agentllm.tools.jira_toolkit import JiraTools
        
        # Create mock issue with sprint data using helper
        sprint_data = [
            "com.atlassian.greenhopper.service.sprint.Sprint@1a2b3c[id=11111,name=Sprint Plugins 19329,startDate=2025-08-01T10:00:00.000Z]",
            "com.atlassian.greenhopper.service.sprint.Sprint@1a2b3c[id=22222,name=Sprint UI 29392,startDate=2025-09-01T13:00:00.000Z]"
        ]
        mock_issue = self._create_mock_issue(
            key="PROJ-123",
            summary="Test issue",
            sprint_data=sprint_data,
        )
        
        mock_jira_client.issue.return_value = mock_issue
        
        toolkit = JiraTools(
            token="test_token",
            server_url="https://mock-jira-url.com",
            extract_sprint_info=True,
        )
        
        result_str = toolkit.extract_sprint_info("PROJ-123")
        result = json.loads(result_str)
        
        assert result["sprint_id"] == "22222"
        assert result["sprint_name"] == "Sprint UI 29392"
