# Home TaskManager

A comprehensive task management system for household employees, built with Notion databases and Python automation. This system manages recurring tasks with themed workdays (Random/Errands on Monday, Cooking on Tuesday, Cleaning on Thursday) and automatically generates actionable tasks for the coming week.

## Overview

The system consists of two Notion databases:
- **Template Tasks**: Stores recurring task definitions with frequency, category, and completion tracking
- **Active Tasks**: Contains actionable tasks generated from templates with planned dates and status tracking

## Features

- **Recurring Task Management**: Define tasks with various frequencies (Daily, Weekly, Monthly, Quarterly, Yearly, Monday/Thursday)
- **Themed Workdays**: Automatic categorization based on work schedule (Monday: Random/Errands, Tuesday: Cooking, Thursday: Cleaning)
- **Week-Ahead Planning**: Generate all tasks for the coming week in advance
- **Completion Tracking**: Automatically update template completion dates based on active task status
- **Duplicate Prevention**: Avoid creating duplicate active tasks
- **Live Notion Integration**: Direct API integration for real-time updates
- **Automated Scheduling**: Built-in scheduler runs weekly on Fridays at 9:00 AM and daily at 6:00 AM
- **Daily Planned Date Review**: Automatically sets planned dates for active tasks that lack them (sets to Thursday of next week)
- **Continuous Operation**: Container runs continuously and handles its own scheduling
- **First-Run Execution**: Automatically runs task generation on first container startup regardless of day

## Architecture

For detailed information about the system architecture, execution flow, and component relationships, see [design.md](design.md).

The system consists of two Notion databases:
- **Template Tasks**: Stores recurring task definitions with frequency, category, and completion tracking
- **Active Tasks**: Contains actionable tasks generated from templates with planned dates and status tracking

## How was this built?
This was built pretty much entirely with vibe coding using [Cursor's IDE](https://cursor.com/?from=home). It was my first time using such a tool, and the fact I could produce this in less than 3 hours is... pretty wild. I did need to jump in and fix mistakes it made, and this included running a debugger to see the actual objects available and how to make sense of them. I could not have done this without my prior skills; though I also could not have used my skills to deliver so much so quickly.

You can see my actual chat with the agent in [cursor_agent_chat.md](cursor_agent_chat.md) if you want. I also had already modeled the data structures in [schemas.md](schemas.md).

## Setup

### Prerequisites

- Python 3.7+ (for local development)
- Docker (for containerized deployment)
- Notion account with API access
- Two Notion databases (Template Tasks and Active Tasks)

### Installation

#### Option 1: Local Development

1. Clone the repository:
```bash
git clone <repository-url>
cd TaskManager
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

#### Option 2: Docker Deployment

1. Clone the repository:
```bash
git clone <repository-url>
cd TaskManager
```

2. Build the Docker image:
```bash
docker build -t notion-home-task-manager .
```

3. Or use Docker Compose:
```bash
docker-compose up --build
```

3. Configure Notion integration:
   - Create a Notion integration at https://www.notion.so/my-integrations
   - Share both databases with your integration
   - Copy the integration token

4. Set up configuration:
   - Create `notion_config.yaml` with your database IDs
   - Set the `NOTION_INTEGRATION_TOKEN` environment variable
   - **Important**: You must create your own Notion databases and configure them in this file
   - Example configuration:
```yaml
template_tasks_db_id: "your_template_database_id_here"
active_tasks_db_id: "your_active_database_id_here"
```

5. Set environment variable:
```bash
export NOTION_INTEGRATION_TOKEN="your_integration_token_here"
```

### ⚠️ Important: Database Configuration Required

**You must create your own Notion databases and configure them in `notion_config.yaml`:**

1. **Create Template Tasks Database**:
   - Create a new Notion database
   - Add the required properties (Name, Category, Frequency, Last Completed, Description, Status)
   - Copy the database ID from the URL

2. **Create Active Tasks Database**:
   - Create a new Notion database
   - Add the required properties (Name, Category, Status, Planned Date, TemplateId, Description)
   - Copy the database ID from the URL

3. **Share with Integration**:
   - Share both databases with your Notion integration
   - Ensure the integration has edit permissions

4. **Update Configuration**:
   - Replace the placeholder values in `notion_config.yaml` with your actual database IDs
   - Set the `NOTION_INTEGRATION_TOKEN` environment variable with your integration token

### Database Schema

#### Template Tasks Database
- **Name** (title): Task name
- **Category** (select): Random/Monday, Cooking/Tuesday, Cleaning/Thursday
- **Frequency** (select): Daily, Weekly, Monthly, Quarterly, Yearly, Monday/Thursday
- **Last Completed** (date): Last completion date (auto-updated)
- **Description** (rich_text): Task description
- **Status** (status): Active, Inactive

#### Active Tasks Database
- **Name** (title): Task name (copied from template)
- **Category** (select): Random/Monday, Cooking/Tuesday, Cleaning/Thursday
- **Status** (status): Not Started, In Progress, Complete
- **Planned Date** (date): Expected completion date
- **TemplateId** (rich_text): Reference to source template task
- **Description** (rich_text): Task description (copied from template)

## Usage

### Weekly Task Generation

The system automatically generates tasks for the coming week every Friday at 9:00 AM. On first startup, it will run immediately regardless of the day to ensure tasks are generated for the current week.

### Daily Planned Date Review

The system automatically reviews active tasks every day at 6:00 AM and sets planned dates for tasks that lack them. This functionality:

- **Identifies Active Tasks**: Finds tasks that are active (not completed) and don't have a planned date
- **Excludes Template Tasks**: Only processes manually created tasks (those without a TemplateId)
- **Sets Planned Dates**: Assigns the Thursday of the coming week as the planned date
- **Ensures Visibility**: Helps ensure all desired tasks show up in the worker's view

#### Manual Run (Local Development)
```bash
python scripts/daily_planned_date_review.py
```

#### Manual Run (Docker)
```bash
docker run --rm \
  -v $(pwd)/notion_config.yaml:/app/notion_config.yaml:ro \
  -e NOTION_INTEGRATION_TOKEN="your_integration_token_here" \
  notion-home-task-manager \
  python scripts/daily_planned_date_review.py
```

#### Manual Run (Local Development)
```bash
python scripts/weekly_rollover/create_active_tasks_from_templates.py
```

#### Manual Run (Docker)
```bash
docker run --rm \
  -v $(pwd)/notion_config.yaml:/app/notion_config.yaml:ro \
  -e NOTION_INTEGRATION_TOKEN="your_integration_token_here" \
  notion-home-task-manager \
  python scripts/weekly_rollover/create_active_tasks_from_templates.py
```

#### Continuous Operation (Docker)
```bash
# Start the scheduler (runs continuously)
docker run -d \
  --name notion-task-manager \
  -v $(pwd)/notion_config.yaml:/app/notion_config.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/state:/app/state \
  -e NOTION_INTEGRATION_TOKEN="your_integration_token_here" \
  --restart unless-stopped \
  notion-home-task-manager
```

#### Docker Compose (Continuous Operation)
```bash
# Start the scheduler (runs continuously)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the scheduler
docker-compose down
```

This script:
1. Fetches all template tasks from Notion
2. Updates "Last Completed" dates based on completed active tasks
3. Syncs select and status options between databases
4. Creates active tasks for the coming week based on frequency and completion history
5. Avoids creating duplicates for existing uncompleted tasks

### Frequency Logic

- **Daily**: Creates tasks for each workday if not completed today
- **Weekly**: Creates one task per week if not completed in the previous week
- **Monthly**: Creates one task per month if not completed in the previous month
- **Quarterly**: Creates one task per quarter if not completed in the previous quarter
- **Yearly**: Creates one task per year if not completed in the previous year
- **Monday/Thursday**: Creates two tasks per week (Monday and Thursday) with appropriate categories

### Monday/Thursday Special Handling

Tasks with "Monday/Thursday" frequency are automatically split into two active tasks:
- One with "Random/Monday" category for Monday
- One with "Cleaning/Thursday" category for Thursday

This allows the same task template to be scheduled for both themed days.

## Scripts

### Runtime Scripts

These scripts are part of the continuous runtime system:

- `scripts/weekly_rollover/create_active_tasks_from_templates.py`: Main script for generating weekly tasks
- `scripts/daily_planned_date_review.py`: Daily script for setting planned dates on active tasks
- `scripts/scheduler.py`: Scheduler that runs task generation weekly on Fridays at 9:00 AM and daily review at 6:00 AM

### Utility Scripts

These scripts are for setup, maintenance, and backup operations (not part of the runtime system):

- `scripts/template_management/copy_template_definitions.py`: Exports template tasks to local YAML for backup
- `scripts/template_management/apply_local_template_definitions.py`: Applies local template definitions to Notion

### Configuration

- `notion_config.yaml`: Notion API configuration
- `requirements.txt`: Python dependencies
- `Dockerfile`: Docker container configuration
- `docker-compose.yml`: Docker Compose configuration for easy deployment

## Dependencies

- `notion-client`: Notion API integration
- `pyyaml`: YAML configuration handling
- `python-dateutil`: Date manipulation and recurrence logic
- `pytz`: Timezone handling
- `schedule`: Task scheduling for automated runs

## Logging

The system includes comprehensive logging for debugging and monitoring:
- Task creation and skipping decisions
- Template completion date updates
- Error handling and recovery
- Frequency and date calculations

## Error Handling

The system includes robust error handling for:
- Notion API rate limits and failures
- Missing or invalid database schemas
- Date parsing and timezone issues
- Duplicate task prevention

## Best Practices

1. **Use Continuous Operation**: Run the container with `--restart unless-stopped` for automatic weekly task generation
2. **Monitor Logs**: Check logs for any issues with task generation or API calls
3. **Backup Templates**: Keep template tasks organized and up-to-date
4. **Review Categories**: Ensure template tasks have appropriate categories for themed days
5. **Schedule Timing**: The scheduler runs every Friday at 9:00 AM UTC - adjust your timezone accordingly

## Troubleshooting

### Common Issues

1. **404 Database Errors**: Ensure databases are shared with your integration
2. **Permission Errors**: Verify integration token and database permissions
3. **Duplicate Tasks**: Check for existing uncompleted tasks before manual creation
4. **Date Issues**: Ensure all dates are timezone-aware (UTC)

### Debug Mode

Enable debug logging by modifying the logging level in the script:
```python
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Add your license information here]

## Support

For issues and questions, please create an issue in the repository or contact [your contact information]. 