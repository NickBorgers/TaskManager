#!/usr/bin/env python3
"""
Daily Planned Date Review for Notion Home Task Manager
Reviews all active tasks and sets planned dates for those that lack them.
Sets the planned date to the Thursday of the coming week.
"""

import os
import sys
import yaml
import logging
import argparse
from datetime import datetime, timedelta, date
import pytz

# Add parent directory to path to import utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.notion_client import create_rate_limited_client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Global variables to be initialized in main()
notion = None
ACTIVE_DB_ID = None
TEMPLATE_ID_PROPERTY = "TemplateId"

def get_active_schema():
    """Retrieve the schema for the active tasks database"""
    logger.info(f"Retrieving active schema from Notion DB {ACTIVE_DB_ID}")
    db = notion.databases.retrieve(database_id=ACTIVE_DB_ID)
    return db["properties"]

def get_active_tasks_without_planned_date():
    """Get all active tasks that don't have a planned date and are not template tasks"""
    logger.info("Querying active tasks without planned dates...")
    
    # Filter for tasks that:
    # 1. Don't have a planned date (or have empty planned date)
    # 2. Are not template tasks (don't have TemplateId property or it's empty)
    # 3. Are active (not completed)
    
    filter_conditions = [
        {"property": "Planned Date", "date": {"is_empty": True}}
    ]
    
    # Add filter for non-template tasks (tasks without TemplateId)
    if TEMPLATE_ID_PROPERTY in get_active_schema():
        filter_conditions.append({
            "property": TEMPLATE_ID_PROPERTY, "rich_text": {"is_empty": True}}
        )
    
    # Add filter for non-completed tasks
    active_schema = get_active_schema()
    if "Status" in active_schema:
        # Get all status options that are not in the "Complete" group
        status_schema = active_schema["Status"]["status"]
        complete_group = None
        for group in status_schema.get("groups", []):
            if group.get("name") == "Complete":
                complete_group = group
                break
        
        if complete_group:
            complete_option_ids = set(complete_group.get("option_ids", []))
            # Get all status options that are NOT in the complete group
            non_complete_options = []
            for option in status_schema.get("options", []):
                if option.get("id") not in complete_option_ids:
                    non_complete_options.append(option.get("name"))
            
            if non_complete_options:
                status_filter = {
                    "or": [{"property": "Status", "status": {"equals": status}} for status in non_complete_options]
                }
                filter_conditions.append(status_filter)
    
    filter_ = {"and": filter_conditions}
    
    results = []
    next_cursor = None
    while True:
        response = notion.databases.query(
            database_id=ACTIVE_DB_ID,
            filter=filter_,
            start_cursor=next_cursor if next_cursor else None
        )
        results.extend(response["results"])
        if response.get("has_more"):
            next_cursor = response["next_cursor"]
        else:
            break
    
    logger.info(f"Found {len(results)} active tasks without planned dates")
    return results

def get_active_tasks_without_category():
    """Get all active tasks that don't have a category and are not template tasks"""
    logger.info("Querying active tasks without categories...")
    
    # Filter for tasks that:
    # 1. Don't have a category (or have empty category)
    # 2. Are not template tasks (don't have TemplateId property or it's empty)
    # 3. Are active (not completed)
    
    filter_conditions = [
        {"property": "Category", "select": {"is_empty": True}}
    ]
    
    # Add filter for non-template tasks (tasks without TemplateId)
    if TEMPLATE_ID_PROPERTY in get_active_schema():
        filter_conditions.append({
            "property": TEMPLATE_ID_PROPERTY, "rich_text": {"is_empty": True}}
        )
    
    # Add filter for non-completed tasks
    active_schema = get_active_schema()
    if "Status" in active_schema:
        # Get all status options that are not in the "Complete" group
        status_schema = active_schema["Status"]["status"]
        complete_group = None
        for group in status_schema.get("groups", []):
            if group.get("name") == "Complete":
                complete_group = group
                break
        
        if complete_group:
            complete_option_ids = set(complete_group.get("option_ids", []))
            # Get all status options that are NOT in the complete group
            non_complete_options = []
            for option in status_schema.get("options", []):
                if option.get("id") not in complete_option_ids:
                    non_complete_options.append(option.get("name"))
            
            if non_complete_options:
                status_filter = {
                    "or": [{"property": "Status", "status": {"equals": status}} for status in non_complete_options]
                }
                filter_conditions.append(status_filter)
    
    filter_ = {"and": filter_conditions}
    
    results = []
    next_cursor = None
    while True:
        response = notion.databases.query(
            database_id=ACTIVE_DB_ID,
            filter=filter_,
            start_cursor=next_cursor if next_cursor else None
        )
        results.extend(response["results"])
        if response.get("has_more"):
            next_cursor = response["next_cursor"]
        else:
            break
    
    logger.info(f"Found {len(results)} active tasks without categories")
    return results

def get_old_incomplete_tasks():
    """Get all active tasks that have a planned date in the past but are not completed"""
    logger.info("Querying old incomplete tasks (planned date in the past)...")
    
    # Calculate yesterday's date (tasks planned for yesterday or earlier are "old")
    yesterday = datetime.now(pytz.UTC).date() - timedelta(days=1)
    
    # Filter for tasks that:
    # 1. Have a planned date in the past (yesterday or earlier)
    # 2. Are not template tasks (don't have TemplateId property or it's empty)
    # 3. Are active (not completed)
    
    filter_conditions = [
        {"property": "Planned Date", "date": {"before": (yesterday + timedelta(days=1)).isoformat()}}
    ]
    
    # Add filter for non-template tasks (tasks without TemplateId)
    active_schema = get_active_schema()
    if TEMPLATE_ID_PROPERTY in active_schema:
        filter_conditions.append({
            "property": TEMPLATE_ID_PROPERTY, "rich_text": {"is_empty": True}}
        )
    
    # Add filter for non-completed tasks
    if "Status" in active_schema:
        # Get all status options that are not in the "Complete" group
        status_schema = active_schema["Status"]["status"]
        complete_group = None
        for group in status_schema.get("groups", []):
            if group.get("name") == "Complete":
                complete_group = group
                break
        
        if complete_group:
            complete_option_ids = set(complete_group.get("option_ids", []))
            # Get all status options that are NOT in the complete group
            non_complete_options = []
            for option in status_schema.get("options", []):
                if option.get("id") not in complete_option_ids:
                    non_complete_options.append(option.get("name"))
            
            if non_complete_options:
                status_filter = {
                    "or": [{"property": "Status", "status": {"equals": status}} for status in non_complete_options]
                }
                filter_conditions.append(status_filter)
    
    filter_ = {"and": filter_conditions}
    
    results = []
    next_cursor = None
    while True:
        response = notion.databases.query(
            database_id=ACTIVE_DB_ID,
            filter=filter_,
            start_cursor=next_cursor if next_cursor else None
        )
        results.extend(response["results"])
        if response.get("has_more"):
            next_cursor = response["next_cursor"]
        else:
            break
    
    logger.info(f"Found {len(results)} old incomplete tasks")
    return results

def get_thursday_of_next_week():
    """Get the date for Thursday of the coming week"""
    today = datetime.now(pytz.UTC).date()
    
    # Find next Thursday
    # Thursday is weekday 3 (Monday=0, Tuesday=1, Wednesday=2, Thursday=3)
    days_until_thursday = (3 - today.weekday()) % 7
    if days_until_thursday == 0:
        # If today is Thursday, get next Thursday
        days_until_thursday = 7
    
    next_thursday = today + timedelta(days=days_until_thursday)
    logger.info(f"Next Thursday is: {next_thursday}")
    return next_thursday

def update_task_planned_date(task_id, planned_date):
    """Update the planned date for a specific task"""
    logger.info(f"Updating planned date for task {task_id} to {planned_date}")
    try:
        notion.pages.update(
            page_id=task_id,
            properties={"Planned Date": {"date": {"start": planned_date.isoformat()}}}
        )
        logger.info(f"Successfully updated planned date for task {task_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to update planned date for task {task_id}: {e}")
        return False

def update_task_category(task_id, category):
    """Update the category for a specific task"""
    logger.info(f"Updating category for task {task_id} to {category}")
    try:
        notion.pages.update(
            page_id=task_id,
            properties={"Category": {"select": {"name": category}}}
        )
        logger.info(f"Successfully updated category for task {task_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to update category for task {task_id}: {e}")
        return False

def main():
    """Main function to review and update planned dates, categories, and old tasks"""
    global notion, ACTIVE_DB_ID

    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Daily Planned Date Review for Notion Home Task Manager")
    parser.add_argument(
        "--config",
        type=str,
        default="notion_config.yaml",
        help="Path to the configuration YAML file (default: notion_config.yaml)"
    )
    args = parser.parse_args()

    # Load config
    if not os.path.exists(args.config):
        logger.error(f"Configuration file not found: {args.config}")
        raise FileNotFoundError(f"Configuration file not found: {args.config}")

    with open(args.config, "r") as f:
        config = yaml.safe_load(f)

    # Get Notion token
    NOTION_TOKEN = os.environ.get("NOTION_INTEGRATION_SECRET")
    if NOTION_TOKEN is None:
        logger.error("NOTION_INTEGRATION_SECRET environment variable not set.")
        raise EnvironmentError("NOTION_INTEGRATION_SECRET environment variable not set.")

    # Get active database ID
    ACTIVE_DB_ID = config.get("active_tasks_db_id")
    if not ACTIVE_DB_ID:
        logger.error(f"active_tasks_db_id must be set in {args.config}")
        raise ValueError(f"active_tasks_db_id must be set in {args.config}")

    # Initialize Notion client
    notion = create_rate_limited_client(auth=NOTION_TOKEN)

    logger.info("Starting daily planned date review...")

    try:
        total_updated = 0
        
        # 1. Handle tasks without planned dates
        logger.info("=== Processing tasks without planned dates ===")
        tasks_without_planned_date = get_active_tasks_without_planned_date()
        
        if tasks_without_planned_date:
            # Get the Thursday of next week
            next_thursday = get_thursday_of_next_week()
            
            # Update each task
            updated_count = 0
            for task in tasks_without_planned_date:
                task_id = task["id"]
                task_name = "Unknown Task"
                title_prop = task.get("properties", {}).get("Task", {}).get("title", [])
                if title_prop and len(title_prop) > 0:
                    task_name = title_prop[0].get("plain_text", "Unknown Task")
                
                logger.info(f"Processing task: {task_name} (ID: {task_id})")
                
                if update_task_planned_date(task_id, next_thursday):
                    updated_count += 1
            
            logger.info(f"Updated {updated_count} out of {len(tasks_without_planned_date)} tasks without planned dates.")
            total_updated += updated_count
        else:
            logger.info("No active tasks found without planned dates")
        
        # 2. Handle tasks without categories
        logger.info("=== Processing tasks without categories ===")
        tasks_without_category = get_active_tasks_without_category()
        
        if tasks_without_category:
            # Update each task to Random/Monday category
            updated_count = 0
            for task in tasks_without_category:
                task_id = task["id"]
                task_name = "Unknown Task"
                title_prop = task.get("properties", {}).get("Task", {}).get("title", [])
                if title_prop and len(title_prop) > 0:
                    task_name = title_prop[0].get("plain_text", "Unknown Task")
                
                logger.info(f"Processing task: {task_name} (ID: {task_id})")
                
                if update_task_category(task_id, "Random/Monday"):
                    updated_count += 1
            
            logger.info(f"Updated {updated_count} out of {len(tasks_without_category)} tasks without categories.")
            total_updated += updated_count
        else:
            logger.info("No active tasks found without categories")
        
        # 3. Handle old incomplete tasks (planned date in the past)
        logger.info("=== Processing old incomplete tasks ===")
        old_incomplete_tasks = get_old_incomplete_tasks()
        
        if old_incomplete_tasks:
            # Get the Thursday of next week
            next_thursday = get_thursday_of_next_week()
            
            # Update each task
            updated_count = 0
            for task in old_incomplete_tasks:
                task_id = task["id"]
                task_name = "Unknown Task"
                title_prop = task.get("properties", {}).get("Task", {}).get("title", [])
                if title_prop and len(title_prop) > 0:
                    task_name = title_prop[0].get("plain_text", "Unknown Task")
                
                logger.info(f"Processing old task: {task_name} (ID: {task_id})")
                
                if update_task_planned_date(task_id, next_thursday):
                    updated_count += 1
            
            logger.info(f"Updated {updated_count} out of {len(old_incomplete_tasks)} old incomplete tasks.")
            total_updated += updated_count
        else:
            logger.info("No old incomplete tasks found")
        
        logger.info(f"Daily planned date review completed. Total tasks updated: {total_updated}")
        
    except Exception as e:
        logger.error(f"Error during daily planned date review: {e}")
        raise

if __name__ == "__main__":
    main()
