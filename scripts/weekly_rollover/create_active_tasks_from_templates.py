import os
import sys
import yaml
import logging
import argparse
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dateutil.parser import isoparse
from datetime import datetime, timedelta, date
import pytz

# Add parent directory to path to import utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from utils.notion_client import create_rate_limited_client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Runtime configuration (initialized in main)
config = None
NOTION_TOKEN = None
TEMPLATE_DB_ID = None
ACTIVE_DB_ID = None
COMPLETED_DB_ID = None
notion = None

TEMPLATE_ID_PROPERTY = "TemplateId"

def get_template_schema():
    logger.info(f"Retrieving template schema from Notion DB {TEMPLATE_DB_ID}")
    db = notion.databases.retrieve(database_id=TEMPLATE_DB_ID)
    return db["properties"]

def get_template_tasks():
    logger.info(f"Querying all template tasks from Notion DB {TEMPLATE_DB_ID}")
    results = []
    next_cursor = None
    while True:
        response = notion.databases.query(
            database_id=TEMPLATE_DB_ID,
            start_cursor=next_cursor if next_cursor else None
        )
        results.extend(response["results"])
        if response.get("has_more"):
            next_cursor = response["next_cursor"]
        else:
            break
    logger.info(f"Fetched {len(results)} template tasks.")
    tasks = []
    for page in results:
        task = {"id": page["id"], "properties": {}}
        for k, v in page["properties"].items():
            if v["type"] == "select":
                task["properties"][k] = v["select"]["name"] if v["select"] else None
            elif v["type"] == "title":
                task["properties"][k] = v["title"][0]["plain_text"] if v["title"] else None
            elif v["type"] == "rich_text":
                task["properties"][k] = v["rich_text"][0]["plain_text"] if v["rich_text"] else None
            elif v["type"] == "url":
                task["properties"][k] = v["url"]
            elif v["type"] == "date":
                task["properties"][k] = v["date"]
            else:
                task["properties"][k] = v.get(v["type"])
        tasks.append(task)
    return tasks

def get_active_schema():
    logger.info(f"Retrieving active schema from Notion DB {ACTIVE_DB_ID}")
    db = notion.databases.retrieve(database_id=ACTIVE_DB_ID)
    return db["properties"]

def sync_options(active_schema, template_schema):
    logger.info("Syncing select and status options between template and active DBs...")
    for name, prop in template_schema.items():
        if name in active_schema and prop["type"] in ("select", "status"):
            active_type = active_schema[name][prop["type"]]
            current_options = {o["name"]: o for o in active_type["options"]}
            new_options = []
            for option in prop.get("options", []):
                if option["name"] not in current_options:
                    new_options.append({"name": option["name"], "color": option["color"]})
            if new_options:
                logger.info(f"Adding new options to {name}: {[o['name'] for o in new_options]}")
                notion.databases.update(
                    database_id=ACTIVE_DB_ID,
                    properties={
                        name: {
                            prop["type"]: {
                                "options": list(current_options.values()) + new_options
                            }
                        }
                    }
                )

def build_active_task_properties(template_task, template_schema, active_schema, now_dt=None):
    mapping = {
        "Task": "Task",
        "Priority": "Priority",
        "Category": "Category",
        "Documentation": "Documentation",
    }
    properties = {}
    if TEMPLATE_ID_PROPERTY in active_schema:
        properties[TEMPLATE_ID_PROPERTY] = {"rich_text": [{"text": {"content": template_task["id"]}}]}
    for t_field, a_field in mapping.items():
        if a_field not in active_schema or t_field not in template_task["properties"]:
            continue
        v = template_task["properties"][t_field]
        prop_type = active_schema[a_field]["type"]
        if prop_type == "select":
            properties[a_field] = {"select": {"name": v}} if v else {"select": None}
        elif prop_type == "status":
            status_options = active_schema[a_field]["status"]["options"]
            default_status = next((o["name"] for o in status_options if o.get("name", "").lower() in ("not started", "todo", "to do")), status_options[0]["name"] if status_options else "Not Started")
            properties[a_field] = {"status": {"name": default_status}}
        elif prop_type == "title":
            properties[a_field] = {"title": [{"text": {"content": v}}]} if v else {"title": []}
        elif prop_type == "rich_text":
            properties[a_field] = {"rich_text": [{"text": {"content": v}}]} if v else {"rich_text": []}
        elif prop_type == "url":
            properties[a_field] = {"url": v}
        else:
            properties[a_field] = {prop_type: v}
    if "Status" in active_schema:
        status_options = active_schema["Status"]["status"]["options"]
        default_status = next((o["name"] for o in status_options if o.get("name", "").lower() in ("not started", "todo", "to do")), status_options[0]["name"] if status_options else "Not Started")
        properties["Status"] = {"status": {"name": default_status}}
    if "CreationDate" in active_schema:
        if now_dt is None:
            current_iso = datetime.utcnow().isoformat()
        else:
            if now_dt.tzinfo is None:
                current_iso = now_dt.replace(tzinfo=pytz.UTC).isoformat()
            else:
                current_iso = now_dt.astimezone(pytz.UTC).isoformat()
        properties["CreationDate"] = {"date": {"start": current_iso}}
    return properties

def get_active_tasks_for_template(template_id):
    # Retrieve all Active Tasks for the given TemplateId
    filter_ = {
        "property": TEMPLATE_ID_PROPERTY,
        "rich_text": {"equals": template_id}
    }
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
    logger.info(f"Found {len(results)} active tasks for template id {template_id}")
    return results

def is_status_complete(page, active_schema):
    props = page.get("properties", {})
    status_prop = props.get("Status")
    if not status_prop or status_prop.get("type") != "status":
        return False
    status_val = status_prop["status"]
    if not status_val:
        return False
    status_id = status_val.get("id")
    # Find the 'Complete' group in the schema
    status_schema = active_schema["Status"]["status"]
    complete_group = None
    for group in status_schema.get("groups", []):
        if group.get("name") == "Complete":
            complete_group = group
            break
    if not complete_group:
        logger.warning("No 'Complete' group found in status schema.")
        return False
    complete_option_ids = set(complete_group.get("option_ids", []))
    return status_id in complete_option_ids

def extract_completed_date(task):
    props = task.get("properties", {})
    completed = props.get("Completed Date")
    if completed and completed.get("type") == "date":
        date_val = completed.get("date")
        if date_val and date_val.get("start"):
            return date_val["start"]
    return None

def create_active_task(template_task, properties):
    """Create an active task."""
    new_page = notion.pages.create(parent={"database_id": ACTIVE_DB_ID}, properties=properties)
    return new_page

def update_template_last_completed(template_task_id, last_completed_date):
    logger.info(f"Updating Last Completed for template {template_task_id} to {last_completed_date}")
    notion.pages.update(
        page_id=template_task_id,
        properties={"Last Completed": {"date": {"start": last_completed_date}}}
    )

def is_task_due(template_task, now=None):
    # Returns a list of (category, due) tuples for which the task should be created
    props = template_task["properties"]
    freq = props.get("Frequency")
    last_completed = props.get("Last Completed")
    if now is None:
        now = datetime.now(pytz.UTC)
    if last_completed and isinstance(last_completed, dict):
        last_completed_date = last_completed.get("start")
        if last_completed_date:
            last_completed_dt = datetime.fromisoformat(last_completed_date)
            if last_completed_dt.tzinfo is None:
                last_completed_dt = last_completed_dt.replace(tzinfo=pytz.UTC)
            else:
                last_completed_dt = last_completed_dt.astimezone(pytz.UTC)
        else:
            last_completed_dt = None
    else:
        last_completed_dt = None
    due = []
    if freq == "Daily":
        if not last_completed_dt or (now.date() > last_completed_dt.date()):
            due.append((props.get("Category"), True))
    elif freq == "Weekly":
        if not last_completed_dt or (now - last_completed_dt >= timedelta(days=7)):
            due.append((props.get("Category"), True))
    elif freq == "Monthly":
        if not last_completed_dt or (now >= last_completed_dt + relativedelta(months=1)):
            due.append((props.get("Category"), True))
    elif freq == "Quarterly":
        if not last_completed_dt or (now >= last_completed_dt + relativedelta(months=3)):
            due.append((props.get("Category"), True))
    elif freq == "Yearly":
        if not last_completed_dt or (now >= last_completed_dt + relativedelta(years=1)):
            due.append((props.get("Category"), True))
    elif freq == "Monday/Friday":
        # Always check both days
        # Monday
        if not last_completed_dt or (now.weekday() == 0 and (not last_completed_dt or now.date() > last_completed_dt.date())):
            due.append(("Random/Monday", True))
        # Friday (renamed from Thursday)
        if not last_completed_dt or (now.weekday() == 4 and (not last_completed_dt or now.date() > last_completed_dt.date())):
            due.append(("Cleaning/Friday", True))
    else:
        # Unknown frequency, always due
        due.append((props.get("Category"), True))
    return [cat for cat, is_due in due if is_due and cat]

def get_uncompleted_active_tasks_for_template_and_category(template_id, category, active_schema):
    # Retrieve all Active Tasks for the given TemplateId and Category that are not in the 'Complete' group
    filter_ = {
        "and": [
            {"property": TEMPLATE_ID_PROPERTY, "rich_text": {"equals": template_id}},
            {"property": "Category", "select": {"equals": category}}
        ]
    }
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
    # Only return those NOT in the Complete group
    uncompleted = [page for page in results if not is_status_complete(page, active_schema)]
    return uncompleted

def get_next_week_dates(today=None):
    today = today or datetime.now(pytz.UTC).date()
    # Define the work week days (Monday=0, Tuesday=1, Friday=4)
    work_days = {
        "Random/Monday": 0,
        "Cooking/Tuesday": 1,
        "Cleaning/Friday": 4,
    }

    # Find the Monday of the current week
    current_monday = today - timedelta(days=today.weekday())

    # If today is Saturday (5) or Sunday (6), schedule for next week
    if today.weekday() >= 5:
        next_monday = current_monday + timedelta(days=7)
        result = {
            "Random/Monday": next_monday,
            "Cooking/Tuesday": next_monday + timedelta(days=1),
            "Cleaning/Friday": next_monday + timedelta(days=4),
        }
        return result

    # Otherwise, only include days that are today or in the future this week
    result = {}
    for category, day_offset in work_days.items():
        # Calculate the date for this day in the current week
        current_week_day = current_monday + timedelta(days=day_offset)

        # Only include days that are today or in the future
        if today <= current_week_day:
            result[category] = current_week_day

    return result

def _parse_args():
    parser = argparse.ArgumentParser(description="Create Active Tasks for the coming week from Notion templates.")
    parser.add_argument("--config", "-c", default="notion_config.yaml", help="Path to YAML config with Notion DB IDs.")
    parser.add_argument(
        "--now",
        help=(
            "Override current time (ISO-8601). Examples: 2025-01-02, 2025-01-02T14:30:00Z, 2025-01-02T14:30:00+00:00"
        ),
    )
    return parser.parse_args()

def _initialise_from_config(config_path):
    global config, NOTION_TOKEN, TEMPLATE_DB_ID, ACTIVE_DB_ID, notion
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Prefer environment variable, fallback to config file
    NOTION_TOKEN = os.environ.get("NOTION_INTEGRATION_SECRET")
    if NOTION_TOKEN is None:
        NOTION_TOKEN = config.get("notion_integration_secret")
    if NOTION_TOKEN is None:
        logger.error("NOTION_INTEGRATION_SECRET not set. Provide via environment variable or notion_integration_secret in config file.")
        raise EnvironmentError("NOTION_INTEGRATION_SECRET not set. Provide via environment variable or notion_integration_secret in config file.")

    TEMPLATE_DB_ID = config.get("template_tasks_db_id")
    ACTIVE_DB_ID = config.get("active_tasks_db_id")
    if not TEMPLATE_DB_ID or not ACTIVE_DB_ID:
        logger.error(f"Both template_tasks_db_id and active_tasks_db_id must be set in {config_path}")
        raise ValueError(f"Both template_tasks_db_id and active_tasks_db_id must be set in {config_path}")

    notion = create_rate_limited_client(auth=NOTION_TOKEN)

def _parse_now(now_str):
    if not now_str:
        return None
    s = now_str.strip()
    try:
        dt = isoparse(s)
    except Exception:
        # Fallback to date-only parsing
        d = date.fromisoformat(s)
        dt = datetime(d.year, d.month, d.day)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    else:
        dt = dt.astimezone(pytz.UTC)
    return dt

def uncompleted_task_exists_for_date(template_id, category, planned_date, active_schema):
    # Check for an uncompleted Active Task for this template, category, and planned date
    filter_ = {
        "and": [
            {"property": TEMPLATE_ID_PROPERTY, "rich_text": {"equals": template_id}},
            {"property": "Category", "select": {"equals": category}},
            {"property": "Planned Date", "date": {"equals": planned_date.isoformat()}}
        ]
    }
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
    # Only return those NOT in the Complete group
    uncompleted = [page for page in results if not is_status_complete(page, active_schema)]
    return bool(uncompleted)

def is_task_due_for_week(template_task, week_start, planned_date):
    # Returns True if the task is due for the week of week_start, for the planned_date
    props = template_task["properties"]
    freq = props.get("Frequency")
    last_completed = props.get("Last Completed")
    if last_completed and isinstance(last_completed, dict):
        # Handle both structures:
        # Correct: {"start": "2025-10-20"} (from get_template_tasks line 65)
        # Wrong: {"date": {"start": "2025-10-20"}} (from old line 590 bug)
        last_completed_date = last_completed.get("start")
        if not last_completed_date and "date" in last_completed:
            # Handle nested structure from the old bug
            last_completed_date = last_completed["date"].get("start") if isinstance(last_completed["date"], dict) else None
        if last_completed_date:
            last_completed_dt = datetime.fromisoformat(last_completed_date)
            if last_completed_dt.tzinfo is None:
                last_completed_dt = last_completed_dt.replace(tzinfo=pytz.UTC)
            else:
                last_completed_dt = last_completed_dt.astimezone(pytz.UTC)
        else:
            last_completed_dt = None
    else:
        last_completed_dt = None
    planned_dt = datetime.combine(planned_date, datetime.min.time(), tzinfo=pytz.UTC)
    if freq == "Daily":
        return not last_completed_dt or (planned_dt.date() > last_completed_dt.date())
    elif freq == "Weekly":
        # Only create if not completed in the week before planned_date
        if not last_completed_dt:
            return True
        last_week_start = planned_dt - timedelta(days=planned_dt.weekday())
        return last_completed_dt < last_week_start
    elif freq == "Monthly":
        if not last_completed_dt:
            return True
        return planned_dt >= last_completed_dt + relativedelta(months=1)
    elif freq == "Quarterly":
        if not last_completed_dt:
            return True
        return planned_dt >= last_completed_dt + relativedelta(months=3)
    elif freq == "Yearly":
        if not last_completed_dt:
            return True
        return planned_dt >= last_completed_dt + relativedelta(years=1)
    elif freq == "Monday/Friday":
        # Always due for both days if not completed on that day
        return not last_completed_dt or (planned_dt.date() > last_completed_dt.date())
    else:
        return True

def main():
    args = _parse_args()
    _initialise_from_config(args.config)
    anchor_now = _parse_now(args.now)
    logger.info("Fetching Template Tasks from Notion...")
    template_schema = get_template_schema()
    template_tasks = get_template_tasks()
    logger.info("Updating Last Completed dates for Template Tasks...")
    active_schema = get_active_schema()

    for template_task in template_tasks:
        active_tasks = get_active_tasks_for_template(template_task["id"])
        most_recent = None
        most_recent_page_id = None
        for page in active_tasks:
            if is_status_complete(page, active_schema):
                completed_date = extract_completed_date(page)
                logger.debug(f"Task {page.get('id')} completed_date: {completed_date}")
                if completed_date and (most_recent is None or completed_date > most_recent):
                    most_recent = completed_date
                    most_recent_page_id = page.get("id")
        if most_recent:
            # Normalize date to include timezone if it doesn't already
            # Notion API returns dates as either "2025-08-21" or "2025-08-21T00:00:00.000Z"
            if 'T' not in most_recent and 'Z' not in most_recent and '+' not in most_recent:
                # Date-only format, convert to datetime with UTC timezone
                date_obj = datetime.fromisoformat(most_recent)
                date_obj = date_obj.replace(tzinfo=pytz.UTC)
                most_recent = date_obj.isoformat()

            update_template_last_completed(template_task["id"], most_recent)
            # Update in-memory template object to reflect the new Last Completed date
            # This ensures is_task_due_for_week() uses current data, not stale data
            # Structure must match how get_template_tasks() extracts dates (line 65: v["date"])
            template_task["properties"]["Last Completed"] = {"start": most_recent}
    logger.info("Syncing select and status options in Active Tasks DB...")
    sync_options(active_schema, template_schema)
    logger.info("Creating Active Tasks for the coming week from templates...")
    week_dates = get_next_week_dates(anchor_now.date() if anchor_now else None)
    week_start = list(week_dates.values())[0]
    for template_task in template_tasks:
        freq = template_task["properties"].get("Frequency")
        # For Monday/Friday, always create both
        if freq == "Monday/Friday":
            for category, planned_date in week_dates.items():
                if category not in ("Random/Monday", "Cleaning/Friday"):
                    continue
                if not is_task_due_for_week(template_task, week_start, planned_date):
                    continue
                task_name = template_task["properties"].get("Task", "Unknown Task")
                if uncompleted_task_exists_for_date(template_task["id"], category, planned_date, active_schema):
                    logger.info(f"Skipping creation for template id {template_task['id']} ('{task_name}') and category {category} for {planned_date} because uncompleted Active Task already exists.")
                    continue
                properties = build_active_task_properties(template_task, template_schema, active_schema, now_dt=anchor_now)
                if TEMPLATE_ID_PROPERTY in active_schema:
                    properties[TEMPLATE_ID_PROPERTY] = {"rich_text": [{"text": {"content": template_task["id"]}}]}
                properties["Category"] = {"select": {"name": category}}
                properties["Planned Date"] = {"date": {"start": planned_date.isoformat()}}
                create_active_task(template_task, properties)
                logger.info(f"Created Active Task '{task_name}' for template id {template_task['id']} with Category {category} and Planned Date {planned_date}")
        elif freq == "Daily":
            # For daily tasks, create for all three workdays
            for category, planned_date in week_dates.items():
                if not is_task_due_for_week(template_task, week_start, planned_date):
                    continue
                task_name = template_task["properties"].get("Task", "Unknown Task")
                if uncompleted_task_exists_for_date(template_task["id"], category, planned_date, active_schema):
                    logger.info(f"Skipping creation for template id {template_task['id']} ('{task_name}') and category {category} for {planned_date} because uncompleted Active Task already exists.")
                    continue
                properties = build_active_task_properties(template_task, template_schema, active_schema, now_dt=anchor_now)
                if TEMPLATE_ID_PROPERTY in active_schema:
                    properties[TEMPLATE_ID_PROPERTY] = {"rich_text": [{"text": {"content": template_task["id"]}}]}
                properties["Category"] = {"select": {"name": category}}
                properties["Planned Date"] = {"date": {"start": planned_date.isoformat()}}
                create_active_task(template_task, properties)
                logger.info(f"Created Active Task '{task_name}' for template id {template_task['id']} with Category {category} and Planned Date {planned_date}")
        else:
            # For other frequencies, match category to day
            for category, planned_date in week_dates.items():
                if template_task["properties"].get("Category") != category:
                    continue
                if not is_task_due_for_week(template_task, week_start, planned_date):
                    continue
                task_name = template_task["properties"].get("Task", "Unknown Task")
                if uncompleted_task_exists_for_date(template_task["id"], category, planned_date, active_schema):
                    logger.info(f"Skipping creation for template id {template_task['id']} ('{task_name}') and category {category} for {planned_date} because uncompleted Active Task already exists.")
                    continue
                properties = build_active_task_properties(template_task, template_schema, active_schema, now_dt=anchor_now)
                if TEMPLATE_ID_PROPERTY in active_schema:
                    properties[TEMPLATE_ID_PROPERTY] = {"rich_text": [{"text": {"content": template_task["id"]}}]}
                properties["Category"] = {"select": {"name": category}}
                properties["Planned Date"] = {"date": {"start": planned_date.isoformat()}}
                create_active_task(template_task, properties)
                logger.info(f"Created Active Task '{task_name}' for template id {template_task['id']} with Category {category} and Planned Date {planned_date}")
    logger.info("Done.")

if __name__ == "__main__":
    main() 