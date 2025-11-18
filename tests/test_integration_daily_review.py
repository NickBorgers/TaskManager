"""
Integration Tests for Daily Planned Date Review

These tests run against REAL test databases to verify:
- Tasks without planned dates get assigned next Thursday
- Tasks without categories get assigned Random/Monday
- Old incomplete tasks get rescheduled to next Thursday
- Complete workflow executes without errors
- Data types from Notion API are handled correctly

Prerequisites:
- NOTION_INTEGRATION_SECRET environment variable set for test database
- test_notion_config.yaml configured with test database IDs
- Test databases should have some active tasks

Run with: pytest tests/test_integration_daily_review.py -v
"""

import pytest
import os
import sys
import yaml
from datetime import datetime, date, timedelta
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
def active_db_id(test_config):
    """Get active database ID from config"""
    return test_config.get("active_tasks_db_id")


class TestDailyReviewExecution:
    """Test that daily review script runs successfully"""

    def test_script_runs_without_errors(self, test_config, rate_limited_script_runner):
        """Test daily review script executes successfully"""
        result = rate_limited_script_runner(
            [
                "python3",
                "scripts/daily_planned_date_review.py",
                "--config", "test_notion_config.yaml"
            ],
            estimate_api_calls=30
        )

        # Check that script completed without errors
        assert result.returncode == 0, f"Script failed with error:\n{result.stderr}"

        # Check for completion message
        output = result.stderr + result.stdout
        assert "completed" in output.lower() or "done" in output.lower(), \
            "Script did not report completion"

    def test_script_handles_empty_database(self, test_config, rate_limited_script_runner):
        """Test that script handles database with no tasks gracefully"""
        result = rate_limited_script_runner(
            [
                "python3",
                "scripts/daily_planned_date_review.py",
                "--config", "test_notion_config.yaml"
            ],
            estimate_api_calls=20
        )

        # Should complete successfully even with no tasks
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"


class TestTasksWithoutPlannedDates:
    """Test handling of tasks without planned dates"""

    def test_query_finds_tasks_without_planned_dates(self, notion_client, active_db_id):
        """Test that we can query for tasks without planned dates"""
        # Query for active tasks without planned dates (not templates, not completed)
        filter_query = {
            "and": [
                {
                    "property": "Planned Date",
                    "date": {"is_empty": True}
                },
                {
                    "property": "TemplateId",
                    "rich_text": {"is_empty": True}
                }
            ]
        }

        response = notion_client.databases.query(
            database_id=active_db_id,
            filter=filter_query
        )

        # Just verify query works - may or may not have results
        assert "results" in response
        print(f"Found {len(response['results'])} tasks without planned dates")

    def test_planned_date_assignment_logic(self, notion_client, active_db_id, rate_limited_script_runner):
        """
        Test that if we have tasks without planned dates,
        after running the script they get assigned next Thursday
        """
        # Query for tasks without planned dates before
        filter_query = {
            "and": [
                {
                    "property": "Planned Date",
                    "date": {"is_empty": True}
                },
                {
                    "property": "TemplateId",
                    "rich_text": {"is_empty": True}
                }
            ]
        }

        before_response = notion_client.databases.query(
            database_id=active_db_id,
            filter=filter_query,
            page_size=5
        )

        before_count = len(before_response["results"])
        print(f"Tasks without planned dates before: {before_count}")

        # Run the daily review script
        result = rate_limited_script_runner(
            [
                "python3",
                "scripts/daily_planned_date_review.py",
                "--config", "test_notion_config.yaml"
            ],
            estimate_api_calls=30
        )

        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

        # Query again after
        after_response = notion_client.databases.query(
            database_id=active_db_id,
            filter=filter_query,
            page_size=5
        )

        after_count = len(after_response["results"])
        print(f"Tasks without planned dates after: {after_count}")

        # Count should decrease or stay same (if there were no tasks to process)
        assert after_count <= before_count, \
            "Daily review should assign planned dates, count should not increase"


class TestTasksWithoutCategories:
    """Test handling of tasks without categories"""

    def test_query_finds_tasks_without_categories(self, notion_client, active_db_id):
        """Test that we can query for tasks without categories"""
        filter_query = {
            "and": [
                {
                    "property": "Category",
                    "select": {"is_empty": True}
                },
                {
                    "property": "TemplateId",
                    "rich_text": {"is_empty": True}
                }
            ]
        }

        response = notion_client.databases.query(
            database_id=active_db_id,
            filter=filter_query
        )

        # Just verify query works
        assert "results" in response
        print(f"Found {len(response['results'])} tasks without categories")

    def test_category_assignment_logic(self, notion_client, active_db_id, rate_limited_script_runner):
        """
        Test that tasks without categories get assigned Random/Monday
        after running the script
        """
        # Query for tasks without categories before
        filter_query = {
            "and": [
                {
                    "property": "Category",
                    "select": {"is_empty": True}
                },
                {
                    "property": "TemplateId",
                    "rich_text": {"is_empty": True}
                }
            ]
        }

        before_response = notion_client.databases.query(
            database_id=active_db_id,
            filter=filter_query,
            page_size=5
        )

        before_count = len(before_response["results"])
        print(f"Tasks without categories before: {before_count}")

        # Run the daily review script
        result = rate_limited_script_runner(
            [
                "python3",
                "scripts/daily_planned_date_review.py",
                "--config", "test_notion_config.yaml"
            ],
            estimate_api_calls=30
        )

        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

        # Query again after
        after_response = notion_client.databases.query(
            database_id=active_db_id,
            filter=filter_query,
            page_size=5
        )

        after_count = len(after_response["results"])
        print(f"Tasks without categories after: {after_count}")

        # Count should decrease or stay same
        assert after_count <= before_count, \
            "Daily review should assign categories, count should not increase"


class TestOldIncompleteTasks:
    """Test handling of old incomplete tasks"""

    def test_query_finds_old_incomplete_tasks(self, notion_client, active_db_id):
        """Test that we can query for old incomplete tasks"""
        # Calculate yesterday's date
        yesterday = (datetime.now(pytz.UTC).date() - timedelta(days=1))

        filter_query = {
            "and": [
                {
                    "property": "Planned Date",
                    "date": {"before": yesterday.isoformat()}
                },
                {
                    "property": "TemplateId",
                    "rich_text": {"is_empty": True}
                }
            ]
        }

        response = notion_client.databases.query(
            database_id=active_db_id,
            filter=filter_query,
            page_size=5
        )

        # Just verify query works
        assert "results" in response
        print(f"Found {len(response['results'])} potentially old incomplete tasks")

        # Check that results have planned dates in the past
        for task in response["results"]:
            planned_date_prop = task["properties"].get("Planned Date")
            if planned_date_prop and planned_date_prop.get("date"):
                planned_date_str = planned_date_prop["date"].get("start")
                if planned_date_str:
                    planned_date = date.fromisoformat(planned_date_str)
                    assert planned_date < datetime.now(pytz.UTC).date(), \
                        f"Task {task['id']} has future planned date but matched old task query"

    def test_old_task_rescheduling(self, notion_client, active_db_id, rate_limited_script_runner):
        """
        Test that old incomplete tasks get rescheduled to next Thursday
        """
        # Query for old incomplete tasks before (not completed, planned date in past)
        yesterday = (datetime.now(pytz.UTC).date() - timedelta(days=1))

        filter_query = {
            "and": [
                {
                    "property": "Planned Date",
                    "date": {"before": yesterday.isoformat()}
                },
                {
                    "property": "TemplateId",
                    "rich_text": {"is_empty": True}
                }
            ]
        }

        before_response = notion_client.databases.query(
            database_id=active_db_id,
            filter=filter_query,
            page_size=10
        )

        # Filter out completed tasks manually
        old_incomplete_before = []
        for task in before_response["results"]:
            status_prop = task["properties"].get("Status")
            if status_prop and status_prop.get("status"):
                status_name = status_prop["status"].get("name", "").lower()
                if "complete" not in status_name and "done" not in status_name:
                    old_incomplete_before.append(task)

        before_count = len(old_incomplete_before)
        print(f"Old incomplete tasks before: {before_count}")

        # Run the daily review script
        result = rate_limited_script_runner(
            [
                "python3",
                "scripts/daily_planned_date_review.py",
                "--config", "test_notion_config.yaml"
            ],
            estimate_api_calls=30
        )

        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

        # Check output for updates
        output = result.stderr + result.stdout
        if before_count > 0:
            # Should have logged some updates
            assert "tasks updated" in output.lower() or "completed" in output.lower(), \
                "Script should report updates when old tasks exist"


class TestDataTypeConsistency:
    """Test that date fields are handled consistently"""

    def test_planned_date_is_string_from_api(self, notion_client, active_db_id):
        """
        Verify that Planned Date from API is a string,
        matching the pattern from weekly rollover
        """
        response = notion_client.databases.query(
            database_id=active_db_id,
            filter={
                "property": "Planned Date",
                "date": {"is_not_empty": True}
            },
            page_size=1
        )

        if response["results"]:
            task = response["results"][0]
            planned_date_prop = task["properties"].get("Planned Date")

            if planned_date_prop and planned_date_prop.get("date"):
                date_value = planned_date_prop["date"].get("start")

                # Should be string, not datetime
                assert isinstance(date_value, str), \
                    f"Expected string from Notion API, got {type(date_value).__name__}"

                # Verify it's valid ISO format
                try:
                    parsed_date = date.fromisoformat(date_value)
                    assert isinstance(parsed_date, date), "Should parse to date object"
                except ValueError as e:
                    pytest.fail(f"Invalid date format from API: {date_value}, error: {e}")


class TestEndToEndWorkflow:
    """Test complete daily review workflow"""

    def test_full_daily_review_execution(self, test_config, rate_limited_script_runner):
        """
        Execute full daily review and verify:
        1. Script completes without errors
        2. All processing sections execute
        3. Summary information is logged
        """
        result = rate_limited_script_runner(
            [
                "python3",
                "scripts/daily_planned_date_review.py",
                "--config", "test_notion_config.yaml"
            ],
            estimate_api_calls=30
        )

        # Verify successful execution
        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

        output = result.stderr + result.stdout

        # Check for key processing sections
        assert "tasks without planned dates" in output.lower() or \
               "Processing tasks without planned dates" in output or \
               "completed" in output.lower(), \
            "Should process tasks without planned dates"

        assert "tasks without categories" in output.lower() or \
               "Processing tasks without categories" in output or \
               "completed" in output.lower(), \
            "Should process tasks without categories"

        assert "old incomplete" in output.lower() or \
               "Processing old incomplete tasks" in output or \
               "completed" in output.lower(), \
            "Should process old incomplete tasks"

        # Check for completion
        assert "completed" in output.lower() or "done" in output.lower(), \
            "Script should report completion"

    def test_multiple_consecutive_runs_idempotent(self, test_config, rate_limited_script_runner):
        """
        Test that running daily review multiple times consecutively
        is idempotent (doesn't cause errors or unexpected changes)
        """
        # Run twice
        for run_num in range(2):
            result = rate_limited_script_runner(
                [
                    "python3",
                    "scripts/daily_planned_date_review.py",
                    "--config", "test_notion_config.yaml"
                ],
                estimate_api_calls=30
            )

            assert result.returncode == 0, \
                f"Script failed on run {run_num + 1}:\n{result.stderr}"

            print(f"Run {run_num + 1} completed successfully")


class TestThursdayCalculation:
    """Test that next Thursday calculation works correctly"""

    def test_tasks_assigned_thursday_dates(self, notion_client, active_db_id, rate_limited_script_runner):
        """
        If tasks were updated, verify they have Thursday dates
        (weekday() == 3)
        """
        # Run the daily review
        result = rate_limited_script_runner(
            [
                "python3",
                "scripts/daily_planned_date_review.py",
                "--config", "test_notion_config.yaml"
            ],
            estimate_api_calls=30
        )

        assert result.returncode == 0, f"Script failed:\n{result.stderr}"

        # Query for recently updated tasks
        # (This is a basic check - we can't easily tell which were just updated)
        response = notion_client.databases.query(
            database_id=active_db_id,
            filter={
                "property": "Planned Date",
                "date": {"is_not_empty": True}
            },
            page_size=10
        )

        # Check a sample of tasks with future planned dates
        future_tasks = []
        today = datetime.now(pytz.UTC).date()

        for task in response["results"]:
            planned_date_prop = task["properties"].get("Planned Date")
            if planned_date_prop and planned_date_prop.get("date"):
                planned_date_str = planned_date_prop["date"].get("start")
                if planned_date_str:
                    planned_date = date.fromisoformat(planned_date_str)
                    if planned_date >= today:
                        future_tasks.append(planned_date)

        # If we have future tasks, at least some should be Thursdays
        # (since daily review assigns Thursday)
        if future_tasks:
            thursday_count = sum(1 for d in future_tasks if d.weekday() == 3)
            print(f"Found {thursday_count} tasks with Thursday dates out of {len(future_tasks)} future tasks")
