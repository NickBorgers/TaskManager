import os
import yaml
import logging
from notion_client import Client
from datetime import datetime
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta, date
import pytz

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load config
with open("notion_config.yaml", "r") as f:
    config = yaml.safe_load(f)

NOTION_TOKEN = os.environ.get("NOTION_INTEGRATION_SECRET")
if NOTION_TOKEN is None:
    logger.error("NOTION_INTEGRATION_SECRET environment variable not set.")
    raise EnvironmentError("NOTION_INTEGRATION_SECRET environment variable not set.")

TEMPLATE_DB_ID = config.get("template_tasks_db_id")
ACTIVE_DB_ID = config.get("active_tasks_db_id")
if not TEMPLATE_DB_ID or not ACTIVE_DB_ID:
    logger.error("Both template_tasks_db_id and active_tasks_db_id must be set in notion_config.yaml")
    raise ValueError("Both template_tasks_db_id and active_tasks_db_id must be set in notion_config.yaml")

notion = Client(auth=NOTION_TOKEN)

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

def build_active_task_properties(template_task, template_schema, active_schema):
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
        properties["CreationDate"] = {"date": {"start": datetime.utcnow().isoformat()}}
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
    elif freq == "Monday/Thursday":
        # Always check both days
        # Monday
        if not last_completed_dt or (now.weekday() == 0 and (not last_completed_dt or now.date() > last_completed_dt.date())):
            due.append(("Random/Monday", True))
        # Thursday
        if not last_completed_dt or (now.weekday() == 3 and (not last_completed_dt or now.date() > last_completed_dt.date())):
            due.append(("Cleaning/Thursday", True))
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

def get_next_week_dates():
    today = datetime.now(pytz.UTC).date()
    # Find next Monday
    next_monday = today + timedelta(days=(7 - today.weekday()) % 7)
    return {
        "Random/Monday": next_monday,
        "Cooking/Tuesday": next_monday + timedelta(days=1),
        "Cleaning/Thursday": next_monday + timedelta(days=3),
    }

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
    elif freq == "Monday/Thursday":
        # Always due for both days if not completed on that day
        return not last_completed_dt or (planned_dt.date() > last_completed_dt.date())
    else:
        return True

def main():
    logger.info("Fetching Template Tasks from Notion...")
    template_schema = get_template_schema()
    template_tasks = get_template_tasks()
    logger.info("Updating Last Completed dates for Template Tasks...")
    active_schema = get_active_schema()
    for template_task in template_tasks:
        active_tasks = get_active_tasks_for_template(template_task["id"])
        most_recent = None
        for page in active_tasks:
            if is_status_complete(page, active_schema):
                completed_date = extract_completed_date(page)
                logger.debug(f"Task {page.get('id')} completed_date: {completed_date}")
                if completed_date and (most_recent is None or completed_date > most_recent):
                    most_recent = completed_date
        if most_recent:
            update_template_last_completed(template_task["id"], most_recent)
    logger.info("Syncing select and status options in Active Tasks DB...")
    sync_options(active_schema, template_schema)
    logger.info("Creating Active Tasks for the coming week from templates...")
    week_dates = get_next_week_dates()
    week_start = list(week_dates.values())[0]
    for template_task in template_tasks:
        freq = template_task["properties"].get("Frequency")
        # For Monday/Thursday, always create both
        if freq == "Monday/Thursday":
            for category, planned_date in week_dates.items():
                if category not in ("Random/Monday", "Cleaning/Thursday"):
                    continue
                if not is_task_due_for_week(template_task, week_start, planned_date):
                    continue
                task_name = template_task["properties"].get("Task", "Unknown Task")
                if uncompleted_task_exists_for_date(template_task["id"], category, planned_date, active_schema):
                    logger.info(f"Skipping creation for template id {template_task['id']} ('{task_name}') and category {category} for {planned_date} because uncompleted Active Task already exists.")
                    continue
                properties = build_active_task_properties(template_task, template_schema, active_schema)
                if TEMPLATE_ID_PROPERTY in active_schema:
                    properties[TEMPLATE_ID_PROPERTY] = {"rich_text": [{"text": {"content": template_task["id"]}}]}
                properties["Category"] = {"select": {"name": category}}
                properties["Planned Date"] = {"date": {"start": planned_date.isoformat()}}
                notion.pages.create(parent={"database_id": ACTIVE_DB_ID}, properties=properties)
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
                properties = build_active_task_properties(template_task, template_schema, active_schema)
                if TEMPLATE_ID_PROPERTY in active_schema:
                    properties[TEMPLATE_ID_PROPERTY] = {"rich_text": [{"text": {"content": template_task["id"]}}]}
                properties["Category"] = {"select": {"name": category}}
                properties["Planned Date"] = {"date": {"start": planned_date.isoformat()}}
                notion.pages.create(parent={"database_id": ACTIVE_DB_ID}, properties=properties)
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
                properties = build_active_task_properties(template_task, template_schema, active_schema)
                if TEMPLATE_ID_PROPERTY in active_schema:
                    properties[TEMPLATE_ID_PROPERTY] = {"rich_text": [{"text": {"content": template_task["id"]}}]}
                properties["Category"] = {"select": {"name": category}}
                properties["Planned Date"] = {"date": {"start": planned_date.isoformat()}}
                notion.pages.create(parent={"database_id": ACTIVE_DB_ID}, properties=properties)
                logger.info(f"Created Active Task '{task_name}' for template id {template_task['id']} with Category {category} and Planned Date {planned_date}")
    logger.info("Done.")

if __name__ == "__main__":
    main() 