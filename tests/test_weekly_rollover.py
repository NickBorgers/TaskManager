#!/usr/bin/env python3
"""
Unit tests for weekly_rollover functionality
Tests the create_active_tasks_from_templates.py module
"""

import pytest
import os
import yaml
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta, date
import pytz
from freezegun import freeze_time

# Mock environment and config before importing the module
with patch.dict(os.environ, {'NOTION_INTEGRATION_SECRET': 'test-token'}, clear=True):
    with patch('builtins.open', MagicMock(side_effect=lambda x, y: MagicMock())):
        with patch('yaml.safe_load', return_value={
            'template_tasks_db_id': 'template-db-id',
            'active_tasks_db_id': 'active-db-id'
        }):
            # Import the functions to test
            import sys
            sys.path.append('scripts/weekly_rollover')
            from create_active_tasks_from_templates import (
                get_template_schema,
                get_template_tasks,
                get_active_schema,
                sync_options,
                build_active_task_properties,
                get_active_tasks_for_template,
                is_status_complete,
                extract_completed_date,
                update_template_last_completed,
                is_task_due,
                get_uncompleted_active_tasks_for_template_and_category,
                get_next_week_dates,
                uncompleted_task_exists_for_date,
                is_task_due_for_week
            )
            # Set up the global variables for testing
            import create_active_tasks_from_templates
            create_active_tasks_from_templates.TEMPLATE_DB_ID = 'template-db-id'
            create_active_tasks_from_templates.ACTIVE_DB_ID = 'active-db-id'
            create_active_tasks_from_templates.NOTION_TOKEN = 'test-token'

class TestConfiguration:
    """Test configuration and environment validation"""
    
    def test_missing_environment_variable(self):
        """Test error handling when NOTION_INTEGRATION_SECRET is not set"""
        # This test documents the expected behavior but can't be easily tested
        # since the error is raised during module import
        # In a real scenario, this would be caught by the calling code
        pass
    
    def test_missing_config_values(self):
        """Test error handling when required config values are missing"""
        # This test documents the expected behavior but can't be easily tested
        # since the error is raised during module import
        # In a real scenario, this would be caught by the calling code
        pass

class TestSchemaRetrieval:
    """Test database schema retrieval functionality"""
    
    @patch('create_active_tasks_from_templates.notion')
    def test_get_template_schema_success(self, mock_notion):
        """Test successful template schema retrieval"""
        mock_response = {
            "properties": {
                "Task": {"title": {}},
                "Frequency": {"select": {}},
                "Category": {"select": {}},
                "Last Completed": {"date": {}}
            }
        }
        mock_notion.databases.retrieve.return_value = mock_response
        
        result = get_template_schema()
        assert result == mock_response["properties"]
        mock_notion.databases.retrieve.assert_called_once_with(database_id='template-db-id')
    
    @patch('create_active_tasks_from_templates.notion')
    def test_get_template_schema_error(self, mock_notion):
        """Test template schema retrieval with API error"""
        mock_notion.databases.retrieve.side_effect = Exception("API Error")
        
        with pytest.raises(Exception, match="API Error"):
            get_template_schema()
    
    @patch('create_active_tasks_from_templates.notion')
    def test_get_active_schema_success(self, mock_notion):
        """Test successful active schema retrieval"""
        mock_response = {
            "properties": {
                "Task": {"title": {}},
                "Status": {"status": {}},
                "Category": {"select": {}},
                "TemplateId": {"rich_text": {}}
            }
        }
        mock_notion.databases.retrieve.return_value = mock_response
        
        result = get_active_schema()
        assert result == mock_response["properties"]
        mock_notion.databases.retrieve.assert_called_once_with(database_id='active-db-id')

class TestTemplateTaskRetrieval:
    """Test template task retrieval functionality"""
    
    @patch('create_active_tasks_from_templates.notion')
    def test_get_template_tasks_single_page(self, mock_notion):
        """Test retrieving template tasks from a single page"""
        mock_response = {
            "results": [
                {
                    "id": "template1",
                    "properties": {
                        "Task": {"type": "title", "title": [{"plain_text": "Test Task"}]},
                        "Frequency": {"type": "select", "select": {"name": "Weekly"}},
                        "Category": {"type": "select", "select": {"name": "Random/Monday"}}
                    }
                }
            ],
            "has_more": False
        }
        mock_notion.databases.query.return_value = mock_response
        
        result = get_template_tasks()
        
        assert len(result) == 1
        assert result[0]["id"] == "template1"
        assert result[0]["properties"]["Task"] == "Test Task"
        assert result[0]["properties"]["Frequency"] == "Weekly"
        mock_notion.databases.query.assert_called_once()
    
    @patch('create_active_tasks_from_templates.notion')
    def test_get_template_tasks_pagination(self, mock_notion):
        """Test retrieving template tasks with pagination"""
        first_response = {
            "results": [{"id": f"template{i}", "properties": {}} for i in range(100)],
            "has_more": True,
            "next_cursor": "cursor1"
        }
        second_response = {
            "results": [{"id": f"template{i}", "properties": {}} for i in range(100, 150)],
            "has_more": False
        }
        
        mock_notion.databases.query.side_effect = [first_response, second_response]
        
        result = get_template_tasks()
        
        assert len(result) == 150
        assert mock_notion.databases.query.call_count == 2
    
    @patch('create_active_tasks_from_templates.notion')
    def test_get_template_tasks_property_extraction(self, mock_notion):
        """Test proper extraction of different property types"""
        mock_response = {
            "results": [
                {
                    "id": "template1",
                    "properties": {
                        "Task": {"type": "title", "title": [{"plain_text": "Test Task"}]},
                        "Priority": {"type": "select", "select": {"name": "High"}},
                        "Description": {"type": "rich_text", "rich_text": [{"plain_text": "Test description"}]},
                        "URL": {"type": "url", "url": "https://example.com"},
                        "DueDate": {"type": "date", "date": {"start": "2024-01-15"}},
                        "EmptyTitle": {"type": "title", "title": []},
                        "EmptySelect": {"type": "select", "select": None},
                        "EmptyRichText": {"type": "rich_text", "rich_text": []}
                    }
                }
            ],
            "has_more": False
        }
        mock_notion.databases.query.return_value = mock_response
        
        result = get_template_tasks()
        
        assert result[0]["properties"]["Task"] == "Test Task"
        assert result[0]["properties"]["Priority"] == "High"
        assert result[0]["properties"]["Description"] == "Test description"
        assert result[0]["properties"]["URL"] == "https://example.com"
        assert result[0]["properties"]["DueDate"] == {"start": "2024-01-15"}
        assert result[0]["properties"]["EmptyTitle"] is None
        assert result[0]["properties"]["EmptySelect"] is None
        assert result[0]["properties"]["EmptyRichText"] is None

class TestActiveTaskRetrieval:
    """Test active task retrieval functionality"""
    
    @patch('create_active_tasks_from_templates.notion')
    def test_get_active_tasks_for_template(self, mock_notion):
        """Test retrieving active tasks for a specific template"""
        mock_response = {
            "results": [
                {
                    "id": "active1",
                    "properties": {
                        "Task": {"title": [{"plain_text": "Active Task 1"}]},
                        "TemplateId": {"rich_text": [{"plain_text": "template1"}]}
                    }
                }
            ],
            "has_more": False
        }
        mock_notion.databases.query.return_value = mock_response
        
        result = get_active_tasks_for_template("template1")
        
        assert len(result) == 1
        assert result[0]["id"] == "active1"
        mock_notion.databases.query.assert_called_once()
    
    @patch('create_active_tasks_from_templates.notion')
    def test_get_uncompleted_active_tasks_for_template_and_category(self, mock_notion):
        """Test retrieving uncompleted active tasks for template and category"""
        mock_response = {
            "results": [
                {
                    "id": "active1",
                    "properties": {
                        "Status": {"status": {"name": "In Progress"}},
                        "TemplateId": {"rich_text": [{"plain_text": "template1"}]},
                        "Category": {"select": {"name": "Random/Monday"}}
                    }
                }
            ],
            "has_more": False
        }
        mock_notion.databases.query.return_value = mock_response
        
        mock_schema = {
            "Status": {
                "status": {
                    "groups": [
                        {"name": "Complete", "option_ids": ["complete1"]}
                    ],
                    "options": [
                        {"id": "active1", "name": "In Progress"},
                        {"id": "complete1", "name": "Done"}
                    ]
                }
            }
        }
        
        result = get_uncompleted_active_tasks_for_template_and_category("template1", "Random/Monday", mock_schema)
        
        assert len(result) == 1
        assert result[0]["id"] == "active1"

class TestStatusCompletion:
    """Test status completion checking functionality"""
    
    def test_is_status_complete_true(self):
        """Test status completion check when task is complete"""
        page = {
            "properties": {
                "Status": {
                    "type": "status",
                    "status": {"id": "complete1"}
                }
            }
        }
        active_schema = {
            "Status": {
                "status": {
                    "groups": [
                        {"name": "Complete", "option_ids": ["complete1", "complete2"]}
                    ]
                }
            }
        }
        
        result = is_status_complete(page, active_schema)
        assert result is True
    
    def test_is_status_complete_false(self):
        """Test status completion check when task is not complete"""
        page = {
            "properties": {
                "Status": {
                    "type": "status",
                    "status": {"id": "active1"}
                }
            }
        }
        active_schema = {
            "Status": {
                "status": {
                    "groups": [
                        {"name": "Complete", "option_ids": ["complete1", "complete2"]}
                    ]
                }
            }
        }
        
        result = is_status_complete(page, active_schema)
        assert result is False
    
    def test_is_status_complete_no_status_property(self):
        """Test status completion check when no status property exists"""
        page = {"properties": {}}
        active_schema = {"Status": {"status": {"groups": []}}}
        
        result = is_status_complete(page, active_schema)
        assert result is False
    
    def test_is_status_complete_no_complete_group(self):
        """Test status completion check when no Complete group exists"""
        page = {
            "properties": {
                "Status": {
                    "type": "status",
                    "status": {"id": "complete1"}
                }
            }
        }
        active_schema = {
            "Status": {
                "status": {
                    "groups": [
                        {"name": "In Progress", "option_ids": ["active1"]}
                    ]
                }
            }
        }
        
        result = is_status_complete(page, active_schema)
        assert result is False

class TestCompletedDateExtraction:
    """Test completed date extraction functionality"""
    
    def test_extract_completed_date_success(self):
        """Test successful completed date extraction"""
        task = {
            "properties": {
                "Completed Date": {
                    "type": "date",
                    "date": {"start": "2024-01-15"}
                }
            }
        }
        
        result = extract_completed_date(task)
        assert result == "2024-01-15"
    
    def test_extract_completed_date_no_date(self):
        """Test completed date extraction when no date exists"""
        task = {
            "properties": {
                "Completed Date": {
                    "type": "date",
                    "date": None
                }
            }
        }
        
        result = extract_completed_date(task)
        assert result is None
    
    def test_extract_completed_date_no_property(self):
        """Test completed date extraction when property doesn't exist"""
        task = {"properties": {}}
        
        result = extract_completed_date(task)
        assert result is None

class TestTemplateLastCompletedUpdate:
    """Test template last completed date update functionality"""
    
    @patch('create_active_tasks_from_templates.notion')
    def test_update_template_last_completed_success(self, mock_notion):
        """Test successful template last completed date update"""
        mock_notion.pages.update.return_value = {"id": "template1"}
        
        update_template_last_completed("template1", "2024-01-15")
        
        mock_notion.pages.update.assert_called_once_with(
            page_id="template1",
            properties={"Last Completed": {"date": {"start": "2024-01-15"}}}
        )

class TestTaskDueLogic:
    """Test task due logic functionality"""
    
    @freeze_time("2024-01-15")  # Monday
    def test_is_task_due_daily_no_last_completed(self):
        """Test daily task due logic when never completed"""
        template_task = {
            "properties": {
                "Frequency": "Daily",
                "Category": "Random/Monday"
            }
        }
        
        result = is_task_due(template_task)
        assert result == ["Random/Monday"]
    
    @freeze_time("2024-01-15")  # Monday
    def test_is_task_due_daily_last_completed_today(self):
        """Test daily task due logic when completed today"""
        template_task = {
            "properties": {
                "Frequency": "Daily",
                "Category": "Random/Monday",
                "Last Completed": {"start": "2024-01-15"}
            }
        }
        
        result = is_task_due(template_task)
        assert result == []
    
    @freeze_time("2024-01-15")  # Monday
    def test_is_task_due_daily_last_completed_yesterday(self):
        """Test daily task due logic when completed yesterday"""
        template_task = {
            "properties": {
                "Frequency": "Daily",
                "Category": "Random/Monday",
                "Last Completed": {"start": "2024-01-14"}
            }
        }
        
        result = is_task_due(template_task)
        assert result == ["Random/Monday"]
    
    @freeze_time("2024-01-15")  # Monday
    def test_is_task_due_weekly_no_last_completed(self):
        """Test weekly task due logic when never completed"""
        template_task = {
            "properties": {
                "Frequency": "Weekly",
                "Category": "Random/Monday"
            }
        }
        
        result = is_task_due(template_task)
        assert result == ["Random/Monday"]
    
    @freeze_time("2024-01-15")  # Monday
    def test_is_task_due_weekly_last_completed_6_days_ago(self):
        """Test weekly task due logic when completed 6 days ago"""
        template_task = {
            "properties": {
                "Frequency": "Weekly",
                "Category": "Random/Monday",
                "Last Completed": {"start": "2024-01-09"}
            }
        }
        
        result = is_task_due(template_task)
        # 6 days ago (2024-01-09) is less than 7 days, so task should not be due
        assert result == []
    
    @freeze_time("2024-01-15")  # Monday
    def test_is_task_due_weekly_last_completed_5_days_ago(self):
        """Test weekly task due logic when completed 5 days ago"""
        template_task = {
            "properties": {
                "Frequency": "Weekly",
                "Category": "Random/Monday",
                "Last Completed": {"start": "2024-01-10"}
            }
        }
        
        result = is_task_due(template_task)
        assert result == []
    
    @freeze_time("2024-01-15")  # Monday
    def test_is_task_due_monday_friday_monday(self):
        """Test Monday/Friday task due logic on Monday"""
        template_task = {
            "properties": {
                "Frequency": "Monday/Friday",
                "Category": "Random/Monday"
            }
        }
        
        result = is_task_due(template_task)
        assert "Random/Monday" in result
        assert "Cleaning/Friday" in result
    
    @freeze_time("2024-01-19")  # Friday
    def test_is_task_due_monday_friday_friday(self):
        """Test Monday/Friday task due logic on Friday"""
        template_task = {
            "properties": {
                "Frequency": "Monday/Friday",
                "Category": "Random/Monday"
            }
        }
        
        result = is_task_due(template_task)
        assert "Random/Monday" in result
        assert "Cleaning/Friday" in result
    
    @freeze_time("2024-01-15")  # Monday
    def test_is_task_due_unknown_frequency(self):
        """Test task due logic with unknown frequency"""
        template_task = {
            "properties": {
                "Frequency": "Unknown",
                "Category": "Random/Monday"
            }
        }
        
        result = is_task_due(template_task)
        assert result == ["Random/Monday"]

class TestWeekDateCalculations:
    """Test week date calculation functionality"""
    
    @freeze_time("2024-01-15")  # Monday
    def test_get_next_week_dates(self):
        """Test next week date calculations"""
        result = get_next_week_dates()
        
        # When today is Monday, next Monday is the same day (2024-01-15)
        expected_monday = date(2024, 1, 15)
        expected_tuesday = date(2024, 1, 16)
        expected_friday = date(2024, 1, 19)
        
        assert result["Random/Monday"] == expected_monday
        assert result["Cooking/Tuesday"] == expected_tuesday
        assert result["Cleaning/Friday"] == expected_friday
    
    @freeze_time("2024-01-19")  # Friday
    def test_get_next_week_dates_from_friday(self):
        """Test next week date calculations when today is Friday"""
        result = get_next_week_dates()
        
        # Should return next Monday (2024-01-22), Tuesday (2024-01-23), Friday (2024-01-26)
        expected_monday = date(2024, 1, 22)
        expected_tuesday = date(2024, 1, 23)
        expected_friday = date(2024, 1, 26)
        
        assert result["Random/Monday"] == expected_monday
        assert result["Cooking/Tuesday"] == expected_tuesday
        assert result["Cleaning/Friday"] == expected_friday

class TestTaskDueForWeek:
    """Test task due for week logic"""
    
    def test_is_task_due_for_week_daily_no_last_completed(self):
        """Test daily task due for week when never completed"""
        template_task = {
            "properties": {
                "Frequency": "Daily",
                "Category": "Random/Monday"
            }
        }
        week_start = date(2024, 1, 22)
        planned_date = date(2024, 1, 22)
        
        result = is_task_due_for_week(template_task, week_start, planned_date)
        assert result is True
    
    def test_is_task_due_for_week_daily_last_completed_same_day(self):
        """Test daily task due for week when completed on planned date"""
        template_task = {
            "properties": {
                "Frequency": "Daily",
                "Category": "Random/Monday",
                "Last Completed": {"start": "2024-01-22"}
            }
        }
        week_start = date(2024, 1, 22)
        planned_date = date(2024, 1, 22)
        
        result = is_task_due_for_week(template_task, week_start, planned_date)
        assert result is False
    
    def test_is_task_due_for_week_weekly_no_last_completed(self):
        """Test weekly task due for week when never completed"""
        template_task = {
            "properties": {
                "Frequency": "Weekly",
                "Category": "Random/Monday"
            }
        }
        week_start = date(2024, 1, 22)
        planned_date = date(2024, 1, 22)
        
        result = is_task_due_for_week(template_task, week_start, planned_date)
        assert result is True
    
    def test_is_task_due_for_week_weekly_last_completed_before_week(self):
        """Test weekly task due for week when completed before week start"""
        template_task = {
            "properties": {
                "Frequency": "Weekly",
                "Category": "Random/Monday",
                "Last Completed": {"start": "2024-01-15"}
            }
        }
        week_start = date(2024, 1, 22)
        planned_date = date(2024, 1, 22)
        
        result = is_task_due_for_week(template_task, week_start, planned_date)
        assert result is True
    
    def test_is_task_due_for_week_weekly_last_completed_in_week(self):
        """Test weekly task due for week when completed during the week"""
        template_task = {
            "properties": {
                "Frequency": "Weekly",
                "Category": "Random/Monday",
                "Last Completed": {"start": "2024-01-23"}
            }
        }
        week_start = date(2024, 1, 22)
        planned_date = date(2024, 1, 25)
        
        result = is_task_due_for_week(template_task, week_start, planned_date)
        assert result is False

    def test_is_task_due_for_week_monthly_last_completed_before_month(self):
        """Test monthly task due for week when completed before month start"""
        template_task = {
            "properties": {
                "Frequency": "Monthly",
                "Category": "Random/Monday",
                "Last Completed": {"start": "2023-12-15"}
            }
        }
        week_start = date(2024, 1, 22)
        planned_date = date(2024, 1, 22)
        
        result = is_task_due_for_week(template_task, week_start, planned_date)
        assert result is True
    
    def test_is_task_due_for_week_monthly_last_completed_in_month(self):
        """Test monthly task due for week when completed during the past month"""
        template_task = {
            "properties": {
                "Frequency": "Monthly",
                "Category": "Random/Monday",
                "Last Completed": {"start": "2023-12-31"}
            }
        }
        week_start = date(2024, 1, 22)
        planned_date = date(2024, 1, 25)
        
        result = is_task_due_for_week(template_task, week_start, planned_date)
        assert result is False

    def test_is_task_due_for_week_quarterly_last_completed_before_quarter(self):
        """Test quarterly task due for week when completed before quarter start"""
        template_task = {
            "properties": {
                "Frequency": "Quarterly",
                "Category": "Random/Monday",
                "Last Completed": {"start": "2023-09-15"}
            }
        }
        week_start = date(2024, 1, 22)
        planned_date = date(2024, 1, 22)
        
        result = is_task_due_for_week(template_task, week_start, planned_date)
        assert result is True
    
    def test_is_task_due_for_week_quarterly_last_completed_in_quarter(self):
        """Test quarterly task due for week when completed during the past quarter"""
        template_task = {
            "properties": {
                "Frequency": "Quarterly",
                "Category": "Random/Monday",
                "Last Completed": {"start": "2023-11-30"}
            }
        }
        week_start = date(2024, 1, 22)
        planned_date = date(2024, 1, 25)
        
        result = is_task_due_for_week(template_task, week_start, planned_date)
        assert result is False

class TestUncompletedTaskExistence:
    """Test uncompleted task existence checking"""
    
    @patch('create_active_tasks_from_templates.notion')
    def test_uncompleted_task_exists_for_date_true(self, mock_notion):
        """Test uncompleted task exists check when task exists"""
        mock_response = {
            "results": [
                {
                    "id": "active1",
                    "properties": {
                        "Status": {"status": {"name": "In Progress"}}
                    }
                }
            ],
            "has_more": False
        }
        mock_notion.databases.query.return_value = mock_response
        
        active_schema = {
            "Status": {
                "status": {
                    "groups": [
                        {"name": "Complete", "option_ids": ["complete1"]}
                    ],
                    "options": [
                        {"id": "active1", "name": "In Progress"},
                        {"id": "complete1", "name": "Done"}
                    ]
                }
            }
        }
        
        result = uncompleted_task_exists_for_date("template1", "Random/Monday", date(2024, 1, 22), active_schema)
        assert result is True
    
    @patch('create_active_tasks_from_templates.notion')
    def test_uncompleted_task_exists_for_date_false(self, mock_notion):
        """Test uncompleted task exists check when no uncompleted task exists"""
        mock_response = {
            "results": [
                {
                    "id": "active1",
                    "properties": {
                        "Status": {
                            "type": "status",
                            "status": {"id": "complete1", "name": "Done"}
                        }
                    }
                }
            ],
            "has_more": False
        }
        mock_notion.databases.query.return_value = mock_response
        
        active_schema = {
            "Status": {
                "status": {
                    "groups": [
                        {"name": "Complete", "option_ids": ["complete1"]}
                    ],
                    "options": [
                        {"id": "active1", "name": "In Progress"},
                        {"id": "complete1", "name": "Done"}
                    ]
                }
            }
        }
        
        result = uncompleted_task_exists_for_date("template1", "Random/Monday", date(2024, 1, 22), active_schema)
        assert result is False

class TestPropertyBuilding:
    """Test active task property building functionality"""
    
    def test_build_active_task_properties_basic(self):
        """Test building basic active task properties"""
        template_task = {
            "id": "template1",
            "properties": {
                "Task": "Test Task",
                "Priority": "High",
                "Category": "Random/Monday"
            }
        }
        template_schema = {
            "Task": {"title": {}},
            "Priority": {"select": {}},
            "Category": {"select": {}}
        }
        active_schema = {
            "Task": {"type": "title", "title": {}},
            "Priority": {"type": "select", "select": {}},
            "Category": {"type": "select", "select": {}},
            "TemplateId": {"type": "rich_text", "rich_text": {}},
            "Status": {"type": "status", "status": {"options": [{"name": "Not Started"}]}},
            "CreationDate": {"type": "date", "date": {}}
        }
        
        result = build_active_task_properties(template_task, template_schema, active_schema)
        
        assert result["Task"]["title"][0]["text"]["content"] == "Test Task"
        assert result["Priority"]["select"]["name"] == "High"
        assert result["Category"]["select"]["name"] == "Random/Monday"
        assert result["TemplateId"]["rich_text"][0]["text"]["content"] == "template1"
        assert result["Status"]["status"]["name"] == "Not Started"
        assert "CreationDate" in result
    
    def test_build_active_task_properties_missing_fields(self):
        """Test building properties when some fields are missing"""
        template_task = {
            "id": "template1",
            "properties": {
                "Task": "Test Task"
                # Missing Priority and Category
            }
        }
        template_schema = {
            "Task": {"title": {}},
            "Priority": {"select": {}},
            "Category": {"select": {}}
        }
        active_schema = {
            "Task": {"type": "title", "title": {}},
            "Priority": {"type": "select", "select": {}},
            "Category": {"type": "select", "select": {}},
            "TemplateId": {"type": "rich_text", "rich_text": {}}
        }
        
        result = build_active_task_properties(template_task, template_schema, active_schema)
        
        assert result["Task"]["title"][0]["text"]["content"] == "Test Task"
        assert "Priority" not in result
        assert "Category" not in result
        assert result["TemplateId"]["rich_text"][0]["text"]["content"] == "template1"
    
    def test_build_active_task_properties_null_values(self):
        """Test building properties with null values"""
        template_task = {
            "id": "template1",
            "properties": {
                "Task": None,
                "Priority": None,
                "Category": "Random/Monday"
            }
        }
        template_schema = {
            "Task": {"title": {}},
            "Priority": {"select": {}},
            "Category": {"select": {}}
        }
        active_schema = {
            "Task": {"type": "title", "title": {}},
            "Priority": {"type": "select", "select": {}},
            "Category": {"type": "select", "select": {}},
            "TemplateId": {"type": "rich_text", "rich_text": {}}
        }
        
        result = build_active_task_properties(template_task, template_schema, active_schema)
        
        assert result["Task"]["title"] == []
        assert result["Priority"]["select"] is None
        assert result["Category"]["select"]["name"] == "Random/Monday"

class TestOptionsSync:
    """Test options synchronization functionality"""
    
    @patch('create_active_tasks_from_templates.notion')
    def test_sync_options_new_select_option(self, mock_notion):
        """Test syncing new select options"""
        template_schema = {
            "Priority": {
                "type": "select",
                "options": [
                    {"name": "High", "color": "red"},
                    {"name": "Medium", "color": "yellow"},
                    {"name": "Low", "color": "green"}
                ]
            }
        }
        active_schema = {
            "Priority": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": "High", "color": "red"},
                        {"name": "Medium", "color": "yellow"}
                    ]
                }
            }
        }
        
        sync_options(active_schema, template_schema)
        
        mock_notion.databases.update.assert_called_once_with(
            database_id='active-db-id',
            properties={
                "Priority": {
                    "select": {
                        "options": [
                            {"name": "High", "color": "red"},
                            {"name": "Medium", "color": "yellow"},
                            {"name": "Low", "color": "green"}
                        ]
                    }
                }
            }
        )
    
    @patch('create_active_tasks_from_templates.notion')
    def test_sync_options_no_new_options(self, mock_notion):
        """Test syncing when no new options are needed"""
        template_schema = {
            "Priority": {
                "type": "select",
                "options": [
                    {"name": "High", "color": "red"},
                    {"name": "Medium", "color": "yellow"}
                ]
            }
        }
        active_schema = {
            "Priority": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": "High", "color": "red"},
                        {"name": "Medium", "color": "yellow"}
                    ]
                }
            }
        }
        
        sync_options(active_schema, template_schema)
        
        mock_notion.databases.update.assert_not_called()

# Fixtures for common test data
@pytest.fixture
def sample_template_task():
    """Sample template task data for testing"""
    return {
        "id": "template-123",
        "properties": {
            "Task": "Sample Template Task",
            "Frequency": "Weekly",
            "Category": "Random/Monday",
            "Priority": "High",
            "Last Completed": {"start": "2024-01-08"}
        }
    }

@pytest.fixture
def sample_active_task():
    """Sample active task data for testing"""
    return {
        "id": "active-123",
        "properties": {
            "Task": {"title": [{"plain_text": "Sample Active Task"}]},
            "Status": {"status": {"name": "In Progress"}},
            "Category": {"select": {"name": "Random/Monday"}},
            "TemplateId": {"rich_text": [{"plain_text": "template-123"}]}
        }
    }

@pytest.fixture
def mock_template_schema():
    """Mock template schema for testing"""
    return {
        "Task": {"title": {}},
        "Frequency": {"select": {}},
        "Category": {"select": {}},
        "Priority": {"select": {}},
        "Last Completed": {"date": {}}
    }

@pytest.fixture
def mock_active_schema():
    """Mock active schema for testing"""
    return {
        "Task": {"title": {}},
        "Status": {"status": {
            "groups": [
                {"name": "Complete", "option_ids": ["complete1", "complete2"]}
            ],
            "options": [
                {"id": "active1", "name": "In Progress"},
                {"id": "complete1", "name": "Done"},
                {"id": "complete2", "name": "Archived"}
            ]
        }},
        "Category": {"select": {}},
        "TemplateId": {"rich_text": {}},
        "CreationDate": {"date": {}}
    }

# Performance tests
class TestPerformance:
    """Test performance characteristics"""
    
    @patch('create_active_tasks_from_templates.get_template_schema')
    @patch('create_active_tasks_from_templates.notion')
    def test_large_template_dataset_pagination(self, mock_notion, mock_get_schema):
        """Test handling of large template datasets with pagination"""
        mock_get_schema.return_value = {}
        
        # Create mock responses for pagination
        first_response = {
            "results": [{"id": f"template{i}", "properties": {}} for i in range(100)],
            "has_more": True,
            "next_cursor": "cursor1"
        }
        second_response = {
            "results": [{"id": f"template{i}", "properties": {}} for i in range(100, 150)],
            "has_more": False
        }
        
        mock_notion.databases.query.side_effect = [first_response, second_response]
        
        result = get_template_tasks()
        
        assert len(result) == 150
        assert mock_notion.databases.query.call_count == 2

if __name__ == "__main__":
    pytest.main([__file__])
