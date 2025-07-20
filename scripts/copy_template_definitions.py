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

def get_schema(database_id):
    db = notion.databases.retrieve(database_id=database_id)
    schema = {}
    for name, prop in db["properties"].items():
        entry = {"type": prop["type"]}
        if prop["type"] == "select":
            entry["options"] = [
                {"name": o["name"], "color": o["color"]} for o in prop["select"]["options"]
            ]
        schema[name] = entry
    return schema

def get_template_tasks(database_id):
    results = []
    next_cursor = None
    while True:
        response = notion.databases.query(
            **{"database_id": database_id, "start_cursor": next_cursor} if next_cursor else {"database_id": database_id}
        )
        results.extend(response["results"])
        if response.get("has_more"):
            next_cursor = response["next_cursor"]
        else:
            break
    # Only keep property values for each task
    tasks = []
    for page in results:
        task = {"id": page["id"], "properties": {}}
        for k, v in page["properties"].items():
            # Only keep the value, not the Notion property metadata
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

def main():
    print(f"Fetching Template Tasks schema and tasks from Notion database: {DATABASE_ID}")
    schema = get_schema(DATABASE_ID)
    tasks = get_template_tasks(DATABASE_ID)
    backup = {"schema": schema, "tasks": tasks}
    with open("template_tasks.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(backup, f, allow_unicode=True, sort_keys=False)
    print("Backup saved to template_tasks.yaml")

if __name__ == "__main__":
    main() 