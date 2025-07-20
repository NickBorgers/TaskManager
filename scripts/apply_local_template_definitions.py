import os
import yaml
from notion_client import Client

# Load config from YAML
with open("notion_config.yaml", "r") as f:
    config = yaml.safe_load(f)

NOTION_TOKEN = os.environ.get("NOTION_INTEGRATION_SECRET")
if NOTION_TOKEN is None:
    raise EnvironmentError("NOTION_INTEGRATION_SECRET environment variable not set.")

DATABASE_ID = config.get("template_tasks_db_id")
if DATABASE_ID is None:
    raise ValueError("template_tasks_db_id not found in notion_config.yaml")

notion = Client(auth=NOTION_TOKEN)

# Load backup
with open("template_tasks.yaml", "r", encoding="utf-8") as f:
    backup = yaml.safe_load(f)

schema = backup["schema"]
tasks = backup["tasks"]

def get_current_schema(database_id):
    db = notion.databases.retrieve(database_id=database_id)
    return db["properties"]

def add_missing_select_options(database_id, schema, current_schema):
    for name, prop in schema.items():
        if prop["type"] == "select":
            current_options = set(o["name"] for o in current_schema[name]["select"]["options"])
            for option in prop.get("options", []):
                if option["name"] not in current_options:
                    print(f"Adding select option '{option['name']}' to '{name}'...")
                    notion.databases.update(
                        database_id=database_id,
                        properties={
                            name: {
                                "select": {
                                    "options": [option]
                                }
                            }
                        }
                    )

def get_existing_task_ids(database_id):
    ids = set()
    id_to_page = {}
    next_cursor = None
    while True:
        response = notion.databases.query(
            **{"database_id": database_id, "start_cursor": next_cursor} if next_cursor else {"database_id": database_id}
        )
        for page in response["results"]:
            ids.add(page["id"])
            id_to_page[page["id"]] = page
        if response.get("has_more"):
            next_cursor = response["next_cursor"]
        else:
            break
    return ids, id_to_page

def build_properties_dict(task, schema):
    properties = {}
    for k, v in task["properties"].items():
        prop_type = schema[k]["type"]
        if prop_type == "select":
            properties[k] = {"select": {"name": v}} if v else {"select": None}
        elif prop_type == "title":
            properties[k] = {"title": [{"text": {"content": v}}]} if v else {"title": []}
        elif prop_type == "rich_text":
            properties[k] = {"rich_text": [{"text": {"content": v}}]} if v else {"rich_text": []}
        elif prop_type == "url":
            properties[k] = {"url": v}
        elif prop_type == "date":
            properties[k] = {"date": v}
        else:
            properties[k] = {prop_type: v}
    return properties

def create_task(database_id, task, schema):
    properties = build_properties_dict(task, schema)
    notion.pages.create(parent={"database_id": database_id}, properties=properties)
    print(f"Created task: {task['id']}")

def update_task(page_id, task, schema):
    properties = build_properties_dict(task, schema)
    notion.pages.update(page_id=page_id, properties=properties)
    print(f"Updated task: {page_id}")

def main():
    print("Syncing schema select options...")
    current_schema = get_current_schema(DATABASE_ID)
    add_missing_select_options(DATABASE_ID, schema, current_schema)
    print("Syncing tasks...")
    existing_ids, id_to_page = get_existing_task_ids(DATABASE_ID)
    for task in tasks:
        if task["id"] not in existing_ids:
            create_task(DATABASE_ID, task, schema)
        else:
            update_task(task["id"], task, schema)
    print("Done.")

if __name__ == "__main__":
    main() 