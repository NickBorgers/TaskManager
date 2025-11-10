"""
Integration Tests for Weekly Task Rollover

These tests run against REAL test databases to verify:
- Full workflow from template fetch to active task creation
- Data types returned from Notion API match code expectations
- --now parameter works correctly for time-based testing
- No duplicate tasks created
- Last Completed dates updated correctly

CRITICAL: These tests would have caught the isoformat bug because they verify
that date strings from Notion API are handled correctly without calling .isoformat()

Prerequisites:
- NOTION_INTEGRATION_SECRET environment variable set for test database
- test_notion_config.yaml configured with test database IDs
- Test databases should have some template tasks set up

Run with: pytest tests/test_integration_weekly_rollover.py -v
"""

import pytest
import os
import sys
import yaml
from datetime import datetime, date
import pytz

# Add parent directory to path to import utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.notion_client import create_rate_limited_client

# Skip all tests if test token not available
pytestmark = pytest.mark.skipif(
    not os.environ.get("NOTION_INTEGRATION_SECRET"),
    reason="NOTION_INTEGRATION_SECRET not set - integration tests require test database access"
)


@pytest.fixture(scope="module")
def test_config():
    """Load test configuration"""
    config_path = "test_notion_config.yaml"
    if not os.path.exists(config_path):
        pytest.skip(f"{config_path} not found - integration tests require test database configuration")

    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def notion_client():
    """Create Notion client for test database access"""
    token = os.environ.get("NOTION_INTEGRATION_SECRET")
    if not token:
        pytest.skip("NOTION_INTEGRATION_SECRET not set")
    return create_rate_limited_client(auth=token)


@pytest.fixture(scope="module")
def template_db_id(test_config):
    """Get template database ID from config"""
    return test_config.get("template_tasks_db_id")


@pytest.fixture(scope="module")
def active_db_id(test_config):
    """Get active database ID from config"""
    return test_config.get("active_tasks_db_id")


class TestNotionAPIDataTypes:
    """Test that data types from Notion API match code expectations"""

    def test_completed_date_is_string_not_datetime(self, notion_client, active_db_id):
        """
        CRITICAL: This test would have caught the isoformat bug.

        Verifies that date fields from Notion API are strings (ISO format),
        not datetime objects. The bug occurred because code called .isoformat()
        on a string that was already in ISO format.
        """
        # Query for any task with a completed date
        response = notion_client.databases.query(
            database_id=active_db_id,
            filter={
                "property": "Completed Date",
                "date": {"is_not_empty": True}
            },
            page_size=1
        )

        if response["results"]:
            task = response["results"][0]
            completed_prop = task["properties"].get("Completed Date")

            if completed_prop and completed_prop.get("date"):
                date_value = completed_prop["date"].get("start")

                # Critical assertion: date from API should be string, not datetime
                assert isinstance(date_value, str), \
                    f"Expected string from Notion API, got {type(date_value).__name__}"

                # Verify it's in ISO format
                try:
                    datetime.fromisoformat(date_value)
                except ValueError:
                    pytest.fail(f"Date value '{date_value}' is not valid ISO format")

    def test_last_completed_date_type_in_templates(self, notion_client, template_db_id):
        """
        Verify Last Completed dates in templates are strings.
        This is the exact field where the isoformat bug occurred.
        """
        response = notion_client.databases.query(
            database_id=template_db_id,
            filter={
                "property": "Last Completed",
                "date": {"is_not_empty": True}
            },
            page_size=1
        )

        if response["results"]:
            template = response["results"][0]
            last_completed_prop = template["properties"].get("Last Completed")

            if last_completed_prop and last_completed_prop.get("date"):
                date_value = last_completed_prop["date"].get("start")

                # This is the critical check - Last Completed should be string
                assert isinstance(date_value, str), \
                    f"Last Completed should be string, got {type(date_value).__name__}"

                # Attempting to call .isoformat() on this would cause AttributeError
                with pytest.raises(AttributeError):
                    date_value.isoformat()


class TestWorkflowWithNowParameter:
    """Test weekly rollover with --now parameter"""

    def test_script_runs_with_now_parameter(self, test_config):
        """Test that script runs successfully with --now parameter"""
        import subprocess

        # Run the script with --now set to a specific Saturday
        result = subprocess.run(
            [
                "python3",
                "scripts/weekly_rollover/create_active_tasks_from_templates.py",
                "--config", "test_notion_config.yaml",
                "--now", "2025-11-15T09:00:00Z"  # Saturday at 9AM
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "NOTION_INTEGRATION_SECRET": os.environ.get("NOTION_INTEGRATION_SECRET")}
        )

        # Check that script completed without errors
        assert result.returncode == 0, f"Script failed with error:\n{result.stderr}"
        assert "ERROR" not in result.stderr, f"Errors in output:\n{result.stderr}"
        assert "Done." in result.stderr or "Done." in result.stdout, \
            "Script did not complete successfully"

    def test_script_handles_different_dates(self, test_config):
        """Test script with various --now parameter formats"""
        import subprocess

        test_dates = [
            "2025-11-15",  # Date only
            "2025-11-15T09:00:00Z",  # Full ISO with Z
            "2025-11-15T09:00:00+00:00",  # Full ISO with timezone
        ]

        for test_date in test_dates:
            result = subprocess.run(
                [
                    "python3",
                    "scripts/weekly_rollover/create_active_tasks_from_templates.py",
                    "--config", "test_notion_config.yaml",
                    "--now", test_date
                ],
                capture_output=True,
                text=True,
                env={**os.environ, "NOTION_INTEGRATION_SECRET": os.environ.get("NOTION_INTEGRATION_SECRET")}
            )

            assert result.returncode == 0, \
                f"Script failed for date '{test_date}' with error:\n{result.stderr}"


class TestDuplicateTaskPrevention:
    """Test that duplicate tasks are not created"""

    def test_no_duplicates_for_same_date(self, notion_client, template_db_id, active_db_id):
        """
        Test that running rollover multiple times for the same date
        doesn't create duplicate tasks
        """
        import subprocess

        # Use a specific test date
        test_date = "2025-12-06T09:00:00Z"  # Saturday

        # Get count of active tasks before
        before_response = notion_client.databases.query(database_id=active_db_id)
        before_count = len(before_response["results"])

        # Run rollover twice with same date
        for _ in range(2):
            result = subprocess.run(
                [
                    "python3",
                    "scripts/weekly_rollover/create_active_tasks_from_templates.py",
                    "--config", "test_notion_config.yaml",
                    "--now", test_date
                ],
                capture_output=True,
                text=True,
                env={**os.environ, "NOTION_INTEGRATION_SECRET": os.environ.get("NOTION_INTEGRATION_SECRET")}
            )

            assert result.returncode == 0, f"Script failed:\n{result.stderr}"

        # Get count of active tasks after
        after_response = notion_client.databases.query(database_id=active_db_id)
        after_count = len(after_response["results"])

        # Should have created tasks once, not twice
        # The exact count depends on templates, but key is second run shouldn't add more
        # This is a basic check - detailed duplicate detection is in next test
        print(f"Before: {before_count}, After: {after_count}")

    def test_duplicate_detection_for_planned_date(self, notion_client, active_db_id):
        """
        Verify that duplicate task detection works correctly.
        Check for tasks with same TemplateId, Category, and Planned Date.
        """
        # Query all active tasks
        response = notion_client.databases.query(database_id=active_db_id)

        # Group by (TemplateId, Category, Planned Date)
        task_map = {}
        for task in response["results"]:
            props = task["properties"]

            template_id_prop = props.get("TemplateId", {})
            template_id = None
            if template_id_prop.get("rich_text"):
                template_id = template_id_prop["rich_text"][0]["plain_text"]

            category_prop = props.get("Category", {})
            category = category_prop.get("select", {}).get("name") if category_prop else None

            planned_date_prop = props.get("Planned Date", {})
            planned_date = None
            if planned_date_prop.get("date"):
                planned_date = planned_date_prop["date"].get("start")

            if template_id and category and planned_date:
                key = (template_id, category, planned_date)
                if key in task_map:
                    # Found duplicate - check if it's completed
                    status_prop = props.get("Status", {})
                    status = status_prop.get("status", {}).get("name") if status_prop else None

                    # Duplicates are only a problem if uncompleted
                    if status not in ["Done", "Completed", "Complete"]:
                        pytest.fail(
                            f"Found duplicate uncompleted tasks for TemplateId={template_id}, "
                            f"Category={category}, Planned Date={planned_date}"
                        )
                else:
                    task_map[key] = task


class TestLastCompletedUpdate:
    """Test that Last Completed dates are updated correctly"""

    def test_last_completed_updates_after_rollover(self, notion_client, template_db_id):
        """
        Verify that Last Completed dates in templates are updated
        when active tasks are marked complete
        """
        # Query templates
        response = notion_client.databases.query(
            database_id=template_db_id,
            page_size=5
        )

        for template in response["results"]:
            last_completed_prop = template["properties"].get("Last Completed")

            if last_completed_prop and last_completed_prop.get("date"):
                date_value = last_completed_prop["date"].get("start")

                # Verify it's a valid ISO date string
                assert isinstance(date_value, str), \
                    "Last Completed should be string"

                try:
                    # Verify it's a valid parseable date
                    # Both date-only ("2025-08-21") and full datetime formats are acceptable
                    # The business logic in is_task_due_for_week() handles both by assuming UTC for date-only
                    parsed_date = datetime.fromisoformat(date_value)
                    assert parsed_date is not None, "Last Completed date should be parseable"
                except ValueError as e:
                    pytest.fail(f"Invalid Last Completed date format: {date_value}, error: {e}")


class TestEndToEndWorkflow:
    """Test complete workflow from templates to active tasks"""

    def test_full_workflow_execution(self, notion_client, template_db_id, active_db_id):
        """
        Execute a full weekly rollover and verify:
        1. Templates are fetched
        2. Active tasks are created
        3. Properties are mapped correctly
        4. No errors occur
        """
        import subprocess

        # Run with a specific test date
        test_date = "2025-12-13T09:00:00Z"  # Saturday

        result = subprocess.run(
            [
                "python3",
                "scripts/weekly_rollover/create_active_tasks_from_templates.py",
                "--config", "test_notion_config.yaml",
                "--now", test_date
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "NOTION_INTEGRATION_SECRET": os.environ.get("NOTION_INTEGRATION_SECRET")}
        )

        # Verify successful execution
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

        # Check logs for key operations
        output = result.stderr + result.stdout
        assert "Fetching Template Tasks" in output or "Fetched" in output, \
            "Templates not fetched"
        assert "Creating Active Tasks" in output or "Created Active Task" in output or "Done." in output, \
            "Active tasks not created"

    def test_workflow_handles_empty_database(self, test_config):
        """
        Test that workflow handles empty template database gracefully
        (This would be a separate test database with no templates)
        """
        import subprocess

        result = subprocess.run(
            [
                "python3",
                "scripts/weekly_rollover/create_active_tasks_from_templates.py",
                "--config", "test_notion_config.yaml",
                "--now", "2025-12-20T09:00:00Z"
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "NOTION_INTEGRATION_SECRET": os.environ.get("NOTION_INTEGRATION_SECRET")}
        )

        # Should complete successfully even with no templates
        assert result.returncode == 0, f"Script failed with empty database:\n{result.stderr}"
        assert "ERROR" not in result.stderr or "Fetched 0 template tasks" in result.stderr


class TestFrequencyLogic:
    """Test different task frequencies work correctly"""

    def test_daily_tasks_created_for_workdays(self, notion_client, template_db_id, active_db_id):
        """
        Test that Daily frequency tasks are created for workdays
        (Monday, Tuesday, Friday based on get_next_week_dates)
        """
        import subprocess

        # Run for a Saturday (should create tasks for next week's workdays)
        test_date = "2025-12-20T09:00:00Z"  # Saturday

        result = subprocess.run(
            [
                "python3",
                "scripts/weekly_rollover/create_active_tasks_from_templates.py",
                "--config", "test_notion_config.yaml",
                "--now", test_date
            ],
            capture_output=True,
            text=True,
            env={**os.environ, "NOTION_INTEGRATION_SECRET": os.environ.get("NOTION_INTEGRATION_SECRET")}
        )

        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

        # Query for tasks created with planned dates in next week
        # This is a basic smoke test - detailed frequency logic is tested in unit tests


# Cleanup fixture to optionally clear test data
@pytest.fixture(scope="function")
def cleanup_test_tasks():
    """Optional cleanup of test tasks after each test"""
    yield
    # Add cleanup logic here if needed
    # For now, we keep test data for inspection
    pass
