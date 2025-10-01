# Home TaskManager

[![Tests](https://img.shields.io/github/actions/workflow/status/NickBorgers/notion-home-task-manager/test.yml?branch=main&style=flat-square&logo=pytest)](https://github.com/NickBorgers/notion-home-task-manager/actions)
[![Docker](https://img.shields.io/badge/docker-available-blue?style=flat-square&logo=docker)](https://hub.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)

A comprehensive task management system for household employees, built with Notion databases and Python automation. This system manages recurring tasks with themed workdays (Random/Errands on Monday, Cooking on Tuesday, Cleaning on Friday) and automatically generates actionable tasks for the coming week.

## Overview

The system consists of two Notion databases:
- **Template Tasks**: Stores recurring task definitions with frequency, category, and completion tracking
- **Active Tasks**: Contains actionable tasks generated from templates with planned dates and status tracking

## Features

- **Recurring Task Management**: Define tasks with various frequencies (Daily, Weekly, Monthly, Quarterly, Yearly, Monday/Friday)
- **Themed Workdays**: Automatic categorization based on work schedule (Monday: Random/Errands, Tuesday: Cooking, Friday: Cleaning)
- **Week-Ahead Planning**: Generate all tasks for the coming week in advance
- **Completion Tracking**: Automatically update template completion dates based on active task status
- **Comment Management**: Automatically copies comments from completed Active Tasks to Template Tasks
- **AI-Powered Summarization**: Uses OpenAI GPT to summarize comments from completed tasks and adds them to new Active Tasks as context
- **Duplicate Prevention**: Avoid creating duplicate active tasks
- **Live Notion Integration**: Direct API integration for real-time updates
- **Automated Scheduling**: Built-in scheduler runs weekly on Saturdays at 9:00 AM and daily at 6:00 AM
- **Daily Planned Date Review**: Automatically sets planned dates for active tasks that lack them, assigns categories to uncategorized tasks, and reschedules old incomplete tasks (sets to Thursday of next week)
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

5. Set environment variables:
```bash
export NOTION_INTEGRATION_TOKEN="your_integration_token_here"
export OPENAI_API_KEY="your_openai_api_key_here"  # Optional, for comment summarization
```

**Note**: The `OPENAI_API_KEY` is optional. If not provided, the system will still work but comment summarization will be disabled.

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
- **Category** (select): Random/Monday, Cooking/Tuesday, Cleaning/Friday
- **Frequency** (select): Daily, Weekly, Monthly, Quarterly, Yearly, Monday/Friday
- **Last Completed** (date): Last completion date (auto-updated)
- **Description** (rich_text): Task description
- **Status** (status): Active, Inactive

#### Active Tasks Database
- **Name** (title): Task name (copied from template)
- **Category** (select): Random/Monday, Cooking/Tuesday, Cleaning/Friday
- **Status** (status): Not Started, In Progress, Complete
- **Planned Date** (date): Expected completion date
- **TemplateId** (rich_text): Reference to source template task
- **Description** (rich_text): Task description (copied from template)

## Usage

### Weekly Task Generation

The system automatically generates tasks for the coming week every Saturday at 9:00 AM. On first startup, it will run immediately regardless of the day to ensure tasks are generated for the current week.

### Daily Planned Date Review

The system automatically reviews active tasks every day at 6:00 AM and performs three types of maintenance:

1. **Tasks Without Planned Dates**: 
   - Finds tasks that are active (not completed) and don't have a planned date
   - Excludes template tasks (those with a TemplateId)
   - Sets planned dates to the Thursday of the coming week
   - Ensures all desired tasks show up in the worker's view

2. **Tasks Without Categories**:
   - Finds tasks that are active and don't have a category assigned
   - Excludes template tasks (those with a TemplateId)
   - Assigns "Random/Monday" category (default for tasks that don't fit specific days)
   - Ensures all tasks have proper categorization

3. **Old Incomplete Tasks**:
   - Finds tasks that have a planned date in the past but are still incomplete
   - Excludes template tasks (those with a TemplateId)
   - Sets planned dates to the Thursday of the coming week
   - Ensures forgotten/missed tasks eventually get completed

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
  -e OPENAI_API_KEY="your_openai_api_key_here" \
  --restart unless-stopped \
  notion-home-task-manager
```

**Note**: The `OPENAI_API_KEY` environment variable is optional. If not provided, comment summarization will be disabled but all other functionality will continue to work.

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
3. Copies comments from the most recently completed Active Task to the Template Task
4. Syncs select and status options between databases
5. Creates active tasks for the coming week based on frequency and completion history
6. Summarizes comments from completed tasks using OpenAI GPT and adds them to new Active Tasks
7. Avoids creating duplicates for existing uncompleted tasks

### Frequency Logic

- **Daily**: Creates tasks for each workday if not completed today
- **Weekly**: Creates one task per week if not completed in the previous week
- **Monthly**: Creates one task per month if not completed in the previous month
- **Quarterly**: Creates one task per quarter if not completed in the previous quarter
- **Yearly**: Creates one task per year if not completed in the previous year
- **Monday/Friday**: Creates two tasks per week (Monday and Friday) with appropriate categories

### Monday/Friday Special Handling

Tasks with "Monday/Friday" frequency are automatically split into two active tasks:
- One with "Random/Monday" category for Monday
- One with "Cleaning/Friday" category for Friday

This allows the same task template to be scheduled for both themed days.

## Scripts

### Runtime Scripts

These scripts are part of the continuous runtime system:

- `scripts/weekly_rollover/create_active_tasks_from_templates.py`: Main script for generating weekly tasks
- `scripts/daily_planned_date_review.py`: Daily script for setting planned dates on active tasks
- `scripts/scheduler.py`: Scheduler that runs task generation weekly on Saturdays at 9:00 AM and daily review at 6:00 AM

### Utility Scripts

These scripts are for setup, maintenance, and backup operations (not part of the runtime system):

- `scripts/template_management/copy_template_definitions.py`: Exports template tasks to local YAML for backup
- `scripts/template_management/apply_local_template_definitions.py`: Applies local template definitions to Notion

### Configuration

- `notion_config.yaml`: Notion API configuration
- `requirements.txt`: Python dependencies
- `Dockerfile`: Docker container configuration
- `docker-compose.yml`: Docker Compose configuration for easy deployment

## Testing

This project uses a **containerized testing approach** that ensures consistent, isolated, and reliable testing without requiring external dependencies like the Notion API.

### 🧪 Test Coverage

The test suite provides comprehensive coverage of the `daily_planned_date_review.py` script:

- **Unit Tests**: Date calculations, configuration validation, schema retrieval
- **Integration Tests**: Task queries, task updates, API interactions
- **Edge Cases**: Large datasets, error scenarios, date boundaries
- **Performance Tests**: Load testing and resource usage monitoring

### 🚀 Running Tests

#### Quick Start (Recommended)
```bash
./run_tests_container.sh
```

#### Using Docker Compose
```bash
docker-compose --profile test up test --build --abort-on-container-exit
```

#### Run Specific Tests
```bash
# Unit tests only
docker run --rm notion-home-task-manager:test pytest tests/ -m unit

# Specific test by name
docker run --rm notion-home-task-manager:test pytest tests/ -k "test_get_thursday"

# With verbose output
docker run --rm notion-home-task-manager:test pytest tests/ -v
```

### 📊 Coverage Reports

After running tests, coverage reports are generated in:
- **HTML Report**: `htmlcov/index.html` (detailed coverage breakdown)
- **Terminal Output**: Coverage summary in console
- **XML Report**: `coverage.xml` (for CI/CD integration)

### 🐳 Containerized Testing Benefits

- **No Local Setup**: No Python installation or virtual environment required
- **Isolated Environment**: Tests run in Docker containers with consistent dependencies
- **No External Dependencies**: All Notion API calls are mocked
- **CI/CD Ready**: Same environment locally and in continuous integration
- **Reproducible Results**: Tests always run in the same environment

### 📁 Test Structure

```
tests/
├── test_daily_planned_date_review.py  # Main test file with all test cases
└── conftest.py                        # Pytest configuration and fixtures

Docker/
├── Dockerfile                         # Multi-stage with test target
├── docker-compose.yml                 # Test service configuration
└── run_tests_container.sh             # Containerized test runner

CI/CD/
└── .github/workflows/test.yml         # GitHub Actions workflow
```

### 🔧 Test Configuration

- **Environment Variables**: All mocked (no `NOTION_INTEGRATION_SECRET` required)
- **External APIs**: Notion API calls mocked with `unittest.mock`
- **Date/Time**: Uses `freezegun` for consistent date testing
- **Coverage**: Automatically generates HTML and XML reports

For detailed testing documentation, see [TESTING.md](TESTING.md).

## Dependencies

- `notion-client`: Notion API integration
- `pyyaml`: YAML configuration handling
- `python-dateutil`: Date manipulation and recurrence logic
- `pytz`: Timezone handling
- `schedule`: Task scheduling for automated runs
- `openai`: OpenAI API integration for comment summarization (optional)

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
5. **Schedule Timing**: The scheduler runs every Saturday at 9:00 AM UTC - adjust your timezone accordingly

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
4. **Add tests if applicable** - Run the test suite to ensure your changes work correctly
5. Submit a pull request

### Development Workflow

1. **Run tests before making changes**:
   ```bash
   ./run_tests_container.sh
   ```

2. **Add new tests for new functionality**:
   - Add test functions to `tests/test_daily_planned_date_review.py`
   - Use appropriate pytest markers (`@pytest.mark.unit`, `@pytest.mark.integration`)
   - Mock any external dependencies

3. **Ensure all tests pass**:
   ```bash
   docker run --rm notion-home-task-manager:test pytest tests/ -v
   ```

4. **Check coverage**:
   ```bash
   docker run --rm notion-home-task-manager:test pytest tests/ --cov=scripts --cov-report=term-missing
   ```

## Releases

This project follows [Semantic Versioning](https://semver.org/) for releases. To create a new release:

### Release Process

1. **Ensure all changes are committed and pushed to main branch**
2. **Create and push a new tag**:
   ```bash
   # For a patch release (bug fixes)
   git tag -a v1.2.2 -m "Fix: brief description of the fix"
   
   # For a minor release (new features, backward compatible)
   git tag -a v1.3.0 -m "Feature: brief description of new feature"
   
   # For a major release (breaking changes)
   git tag -a v2.0.0 -m "Breaking: brief description of breaking changes"
   ```

3. **Push the tag to trigger automated builds**:
   ```bash
   git push origin v1.3.0
   ```

4. **Verify the release**:
   - Check that the GitHub Actions workflow builds and pushes the Docker image
   - Verify the new Docker image is available on Docker Hub
   - Update any deployment configurations to use the new version

### Version Guidelines

- **Patch (1.2.1 → 1.2.2)**: Bug fixes and minor improvements
- **Minor (1.2.1 → 1.3.0)**: New features that are backward compatible
- **Major (1.2.1 → 2.0.0)**: Breaking changes or major architectural changes

### Automated Release Process

When a tag is pushed, the GitHub Actions workflow automatically:
1. Builds the Docker image for multiple platforms (linux/amd64, linux/arm64)
2. Pushes the image to Docker Hub with appropriate tags
3. Creates a `latest` tag for the most recent version

## License

[Add your license information here]

## Support

For issues and questions, please create an issue in the repository or contact [your contact information]. 