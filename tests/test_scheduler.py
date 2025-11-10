"""
Tests for scripts/scheduler.py

These tests verify the scheduler's core runtime logic, including:
- Weekly task generation scheduling
- Daily review scheduling
- First-run detection and execution
- Error handling and recovery
"""

import pytest
from unittest.mock import patch, MagicMock, mock_open, call
from datetime import datetime
import pytz
import os
import sys

# Add project root to path (same as scheduler.py does)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Mock the schedule library before importing scheduler
sys.modules['schedule'] = MagicMock()

# Mock the task generation and daily review modules
sys.modules['scripts.weekly_rollover.create_active_tasks_from_templates'] = MagicMock()
sys.modules['scripts.daily_planned_date_review'] = MagicMock()

# Now we can import scheduler
from scripts import scheduler


class TestRunWeeklyTasks:
    """Test the run_weekly_tasks function"""

    @patch('scripts.scheduler.run_task_generation')
    @patch('scripts.scheduler.logger')
    def test_successful_execution(self, mock_logger, mock_run_gen):
        """Test successful weekly task generation"""
        mock_run_gen.return_value = None

        scheduler.run_weekly_tasks()

        mock_run_gen.assert_called_once()
        mock_logger.info.assert_any_call("Starting weekly task generation...")
        mock_logger.info.assert_any_call("Weekly task generation completed successfully")

    @patch('scripts.scheduler.run_task_generation')
    @patch('scripts.scheduler.logger')
    def test_error_handling(self, mock_logger, mock_run_gen):
        """Test error handling doesn't crash scheduler"""
        mock_run_gen.side_effect = Exception("Test error")

        # Should not raise exception
        scheduler.run_weekly_tasks()

        mock_run_gen.assert_called_once()
        mock_logger.error.assert_called_once()
        assert "Error during weekly task generation" in str(mock_logger.error.call_args)


class TestRunDailyPlannedDateReview:
    """Test the run_daily_planned_date_review function"""

    @patch('scripts.scheduler.daily_planned_date_review_main')
    @patch('scripts.scheduler.logger')
    def test_successful_execution(self, mock_logger, mock_daily):
        """Test successful daily review"""
        mock_daily.return_value = None

        scheduler.run_daily_planned_date_review()

        mock_daily.assert_called_once()
        mock_logger.info.assert_any_call("Starting daily planned date review...")
        mock_logger.info.assert_any_call("Daily planned date review completed successfully")

    @patch('scripts.scheduler.daily_planned_date_review_main')
    @patch('scripts.scheduler.logger')
    def test_error_handling(self, mock_logger, mock_daily):
        """Test error handling doesn't crash scheduler"""
        mock_daily.side_effect = Exception("Test error")

        # Should not raise exception
        scheduler.run_daily_planned_date_review()

        mock_daily.assert_called_once()
        mock_logger.error.assert_called_once()
        assert "Error during daily planned date review" in str(mock_logger.error.call_args)


class TestScheduleWeeklyRun:
    """Test the schedule_weekly_run function"""

    @patch('scripts.scheduler.schedule')
    @patch('scripts.scheduler.logger')
    def test_schedules_saturday_9am(self, mock_logger, mock_schedule):
        """Test that weekly run is scheduled for Saturday 9AM"""
        mock_job = MagicMock()
        mock_schedule.every.return_value.saturday.at.return_value.do.return_value = mock_job

        scheduler.schedule_weekly_run()

        mock_schedule.every.return_value.saturday.at.assert_called_once_with("09:00")
        mock_schedule.every.return_value.saturday.at.return_value.do.assert_called_once()
        mock_logger.info.assert_called_once_with("Scheduled weekly task generation for Saturday at 9:00 AM")


class TestScheduleDailyRun:
    """Test the schedule_daily_run function"""

    @patch('scripts.scheduler.schedule')
    @patch('scripts.scheduler.logger')
    def test_schedules_daily_6am(self, mock_logger, mock_schedule):
        """Test that daily review is scheduled for 6AM"""
        mock_job = MagicMock()
        mock_schedule.every.return_value.day.at.return_value.do.return_value = mock_job

        scheduler.schedule_daily_run()

        mock_schedule.every.return_value.day.at.assert_called_once_with("06:00")
        mock_schedule.every.return_value.day.at.return_value.do.assert_called_once()
        mock_logger.info.assert_called_once_with("Scheduled daily planned date review for 6:00 AM every day")


class TestFirstRunDetection:
    """Test first-run detection and marking"""

    @patch('os.path.exists')
    def test_is_first_run_true(self, mock_exists):
        """Test is_first_run returns True when marker doesn't exist"""
        mock_exists.return_value = False

        result = scheduler.is_first_run()

        assert result is True
        mock_exists.assert_called_once_with("/app/state/.first_run_complete")

    @patch('os.path.exists')
    def test_is_first_run_false(self, mock_exists):
        """Test is_first_run returns False when marker exists"""
        mock_exists.return_value = True

        result = scheduler.is_first_run()

        assert result is False
        mock_exists.assert_called_once_with("/app/state/.first_run_complete")

    @patch('builtins.open', new_callable=mock_open)
    @patch('scripts.scheduler.logger')
    def test_mark_first_run_complete_success(self, mock_logger, mock_file):
        """Test successfully marking first run complete"""
        scheduler.mark_first_run_complete()

        mock_file.assert_called_once_with("/app/state/.first_run_complete", 'w')
        handle = mock_file()
        handle.write.assert_called_once()
        assert "First run completed at" in handle.write.call_args[0][0]
        mock_logger.info.assert_called_once_with("Marked first run as complete")

    @patch('builtins.open', side_effect=Exception("Disk error"))
    @patch('scripts.scheduler.logger')
    def test_mark_first_run_complete_error(self, mock_logger, mock_file):
        """Test error handling when marking first run fails"""
        scheduler.mark_first_run_complete()

        mock_logger.warning.assert_called_once()
        assert "Could not create marker file" in str(mock_logger.warning.call_args)


class TestRunImmediatelyIfNeeded:
    """Test immediate execution logic for weekly tasks"""

    @patch('scripts.scheduler.is_first_run')
    @patch('scripts.scheduler.run_weekly_tasks')
    @patch('scripts.scheduler.mark_first_run_complete')
    @patch('scripts.scheduler.logger')
    def test_first_run_executes_immediately(self, mock_logger, mock_mark, mock_run, mock_is_first):
        """Test that first run executes task generation immediately"""
        mock_is_first.return_value = True

        scheduler.run_immediately_if_needed()

        mock_run.assert_called_once()
        mock_mark.assert_called_once()
        mock_logger.info.assert_any_call("First time running - executing task generation immediately")

    @patch('scripts.scheduler.is_first_run')
    @patch('scripts.scheduler.run_weekly_tasks')
    @patch('scripts.scheduler.datetime')
    @patch('scripts.scheduler.logger')
    def test_saturday_after_9am_executes(self, mock_logger, mock_datetime, mock_run, mock_is_first):
        """Test Saturday after 9AM executes task generation"""
        mock_is_first.return_value = False
        # Saturday (5) at 10:00 AM UTC
        mock_now = MagicMock()
        mock_now.weekday.return_value = 5
        mock_now.hour = 10
        mock_datetime.now.return_value = mock_now

        scheduler.run_immediately_if_needed()

        mock_run.assert_called_once()
        mock_logger.info.assert_any_call("It's Saturday after 9:00 AM - running task generation immediately")

    @patch('scripts.scheduler.is_first_run')
    @patch('scripts.scheduler.run_weekly_tasks')
    @patch('scripts.scheduler.datetime')
    @patch('scripts.scheduler.logger')
    def test_saturday_before_9am_waits(self, mock_logger, mock_datetime, mock_run, mock_is_first):
        """Test Saturday before 9AM doesn't execute"""
        mock_is_first.return_value = False
        # Saturday (5) at 8:00 AM UTC
        mock_now = MagicMock()
        mock_now.weekday.return_value = 5
        mock_now.hour = 8
        mock_now.strftime.return_value = "2024-01-13 08:00:00 UTC"
        mock_datetime.now.return_value = mock_now

        scheduler.run_immediately_if_needed()

        mock_run.assert_not_called()
        mock_logger.info.assert_any_call("It's Saturday but before 9:00 AM. Current time: 2024-01-13 08:00:00 UTC")

    @patch('scripts.scheduler.is_first_run')
    @patch('scripts.scheduler.run_weekly_tasks')
    @patch('scripts.scheduler.datetime')
    @patch('scripts.scheduler.logger')
    def test_monday_does_not_execute(self, mock_logger, mock_datetime, mock_run, mock_is_first):
        """Test Monday doesn't execute task generation"""
        mock_is_first.return_value = False
        # Monday (0) at 10:00 AM UTC
        mock_now = MagicMock()
        mock_now.weekday.return_value = 0
        mock_now.strftime.return_value = "Monday"
        mock_datetime.now.return_value = mock_now

        scheduler.run_immediately_if_needed()

        mock_run.assert_not_called()
        mock_logger.info.assert_any_call("Not Saturday. Current day: Monday")


class TestRunDailyReviewImmediatelyIfNeeded:
    """Test immediate execution logic for daily review"""

    @patch('scripts.scheduler.run_daily_planned_date_review')
    @patch('scripts.scheduler.datetime')
    @patch('scripts.scheduler.logger')
    def test_after_6am_executes(self, mock_logger, mock_datetime, mock_run):
        """Test after 6AM executes daily review"""
        mock_now = MagicMock()
        mock_now.hour = 10
        mock_datetime.now.return_value = mock_now

        scheduler.run_daily_review_immediately_if_needed()

        mock_run.assert_called_once()
        mock_logger.info.assert_called_once_with("It's past 6:00 AM - running daily planned date review immediately")

    @patch('scripts.scheduler.run_daily_planned_date_review')
    @patch('scripts.scheduler.datetime')
    @patch('scripts.scheduler.logger')
    def test_before_6am_waits(self, mock_logger, mock_datetime, mock_run):
        """Test before 6AM doesn't execute"""
        mock_now = MagicMock()
        mock_now.hour = 5
        mock_now.strftime.return_value = "2024-01-13 05:00:00 UTC"
        mock_datetime.now.return_value = mock_now

        scheduler.run_daily_review_immediately_if_needed()

        mock_run.assert_not_called()
        mock_logger.info.assert_called_once_with("It's before 6:00 AM. Current time: 2024-01-13 05:00:00 UTC")

    @patch('scripts.scheduler.run_daily_planned_date_review')
    @patch('scripts.scheduler.datetime')
    @patch('scripts.scheduler.logger')
    def test_exactly_6am_executes(self, mock_logger, mock_datetime, mock_run):
        """Test exactly 6AM executes daily review"""
        mock_now = MagicMock()
        mock_now.hour = 6
        mock_datetime.now.return_value = mock_now

        scheduler.run_daily_review_immediately_if_needed()

        mock_run.assert_called_once()


class TestMainFunction:
    """Test the main scheduler orchestration function"""

    @patch('scripts.scheduler.time.sleep', side_effect=KeyboardInterrupt)
    @patch('scripts.scheduler.schedule.run_pending')
    @patch('scripts.scheduler.schedule_daily_run')
    @patch('scripts.scheduler.schedule_weekly_run')
    @patch('scripts.scheduler.run_daily_review_immediately_if_needed')
    @patch('scripts.scheduler.run_immediately_if_needed')
    @patch('scripts.scheduler.logger')
    def test_main_orchestration(self, mock_logger, mock_run_imm, mock_run_daily_imm,
                               mock_sched_weekly, mock_sched_daily, mock_run_pending, mock_sleep):
        """Test main function orchestrates all components"""
        scheduler.main()

        # Verify all initialization functions called
        mock_run_imm.assert_called_once()
        mock_run_daily_imm.assert_called_once()
        mock_sched_weekly.assert_called_once()
        mock_sched_daily.assert_called_once()

        # Verify startup message
        mock_logger.info.assert_any_call("Starting Notion Home Task Manager Scheduler")
        mock_logger.info.assert_any_call("Scheduler is running. Press Ctrl+C to stop.")

        # Verify loop started
        mock_run_pending.assert_called()
        mock_sleep.assert_called()

    @patch('scripts.scheduler.time.sleep')
    @patch('scripts.scheduler.schedule.run_pending')
    @patch('scripts.scheduler.schedule_daily_run')
    @patch('scripts.scheduler.schedule_weekly_run')
    @patch('scripts.scheduler.run_daily_review_immediately_if_needed')
    @patch('scripts.scheduler.run_immediately_if_needed')
    @patch('scripts.scheduler.logger')
    def test_main_keyboard_interrupt_handling(self, mock_logger, mock_run_imm, mock_run_daily_imm,
                                              mock_sched_weekly, mock_sched_daily, mock_run_pending, mock_sleep):
        """Test main handles KeyboardInterrupt gracefully"""
        mock_sleep.side_effect = KeyboardInterrupt()

        scheduler.main()

        mock_logger.info.assert_any_call("Scheduler stopped by user")

    @patch('scripts.scheduler.time.sleep')
    @patch('scripts.scheduler.schedule.run_pending')
    @patch('scripts.scheduler.schedule_daily_run')
    @patch('scripts.scheduler.schedule_weekly_run')
    @patch('scripts.scheduler.run_daily_review_immediately_if_needed')
    @patch('scripts.scheduler.run_immediately_if_needed')
    @patch('scripts.scheduler.logger')
    def test_main_handles_scheduler_errors(self, mock_logger, mock_run_imm, mock_run_daily_imm,
                                           mock_sched_weekly, mock_sched_daily, mock_run_pending, mock_sleep):
        """Test main logs and raises scheduler errors"""
        test_error = Exception("Scheduler malfunction")
        mock_sleep.side_effect = test_error

        with pytest.raises(Exception) as exc_info:
            scheduler.main()

        assert str(exc_info.value) == "Scheduler malfunction"
        mock_logger.error.assert_called_once()
        assert "Scheduler error" in str(mock_logger.error.call_args)
