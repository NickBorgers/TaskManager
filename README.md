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

## Architecture

```
Template Tasks (Notion DB)
├── Task definitions with frequency, category, last completed date
└── Schema with select options for Category, Frequency, Status

Active Tasks (Notion DB)
├── Generated actionable tasks with planned dates
├── Status tracking (Not Started, In Progress, Complete)
└── Links back to template tasks via TemplateId property
```

## Setup

### Prerequisites

- Python 3.7+
- Notion account with API access
- Two Notion databases (Template Tasks and Active Tasks)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd TaskManager
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure Notion integration:
   - Create a Notion integration at https://www.notion.so/my-integrations
   - Share both databases with your integration
   - Copy the integration token

4. Set up configuration:
   - Create `notion_config.yaml` with your database IDs and integration token
   - Example configuration:
```yaml
notion:
  integration_token: "your_integration_token_here"
  template_database_id: "your_template_db_id"
  active_database_id: "your_active_db_id"
```

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

The main script generates tasks for the coming week:

```bash
python scripts/weekly_rollover/create_active_tasks_from_templates.py
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

### Main Scripts

- `scripts/weekly_rollover/create_active_tasks_from_templates.py`: Main script for generating weekly tasks

### Configuration

- `notion_config.yaml`: Notion API configuration
- `requirements.txt`: Python dependencies

## Dependencies

- `notion-client`: Notion API integration
- `pyyaml`: YAML configuration handling
- `python-dateutil`: Date manipulation and recurrence logic
- `pytz`: Timezone handling

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

1. **Run Weekly**: Execute the main script weekly to generate tasks for the coming week
2. **Monitor Logs**: Check logs for any issues with task generation or API calls
3. **Backup Templates**: Keep template tasks organized and up-to-date
4. **Review Categories**: Ensure template tasks have appropriate categories for themed days

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