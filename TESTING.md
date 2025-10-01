# Testing Guide

## Overview

This project uses a **containerized testing approach** to ensure consistent, isolated, and reliable testing. There are two types of tests:

1. **Unit Tests** - Automated tests that mock external dependencies (Notion API, OpenAI API)
2. **Integration Tests** - Manual tests that use real test databases and APIs

## 🐳 Containerized Testing Benefits

- **Isolated Environment**: Tests run in Docker containers, ensuring consistency across different machines
- **No External Dependencies**: All external APIs and services are mocked
- **No Local Setup**: No need to install Python, packages, or configure environment variables
- **CI/CD Ready**: Same environment locally and in continuous integration
- **Reproducible**: Tests always run in the same environment

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose installed
- No Python installation required locally

### Run All Tests
```bash
./run_tests_container.sh
```

### Run Tests with Docker Compose
```bash
docker-compose --profile test up test --build --abort-on-container-exit
```

### Run Specific Tests
```bash
# Run unit tests only
docker run --rm notion-home-task-manager:test pytest tests/ -m unit

# Run specific test by name
docker run --rm notion-home-task-manager:test pytest tests/ -k "test_get_thursday"

# Run with verbose output
docker run --rm notion-home-task-manager:test pytest tests/ -v
```

## 📁 Test Structure

```
tests/
├── test_daily_planned_date_review.py  # Main test file with all test cases
└── conftest.py                        # Pytest configuration and fixtures

Docker/
├── Dockerfile                         # Multi-stage Dockerfile with test target
├── docker-compose.yml                 # Test service configuration
└── run_tests_container.sh             # Containerized test runner

CI/CD/
└── .github/workflows/test.yml         # GitHub Actions workflow
```

## 🧪 Test Categories

### 1. Unit Tests
- **Date Calculations**: Thursday calculation logic
- **Configuration**: Environment and config file validation
- **Schema Retrieval**: Database schema handling

### 2. Integration Tests
- **Task Queries**: Filtering and querying tasks
- **Task Updates**: Updating planned dates and categories
- **API Interactions**: Mocked Notion API calls

### 3. Edge Cases
- **Large Datasets**: Pagination handling
- **Error Scenarios**: API failures and malformed data
- **Date Boundaries**: Year boundaries and leap years

## 🔧 Test Configuration

### Environment Variables
Tests use mocked environment variables:
- `NOTION_INTEGRATION_SECRET=test-token` (mocked)
- `PYTHONPATH=/app`
- `PYTHONUNBUFFERED=1`

### Mocked Dependencies
- **Notion API**: All API calls are mocked with `unittest.mock`
- **Config Files**: `notion_config.yaml` is mocked
- **Environment Variables**: `NOTION_INTEGRATION_SECRET` is mocked
- **Date/Time**: Uses `freezegun` for consistent date testing

## 📊 Coverage Reports

After running tests, coverage reports are generated in:
- **HTML Report**: `htmlcov/index.html` (detailed coverage breakdown)
- **Terminal Output**: Coverage summary in console
- **XML Report**: `coverage.xml` (for CI/CD integration)

### View Coverage Report
```bash
# Open in browser (Linux)
xdg-open htmlcov/index.html

# Open in browser (macOS)
open htmlcov/index.html
```

## 🏗️ Docker Configuration

### Multi-Stage Dockerfile
```dockerfile
# Base stage with shared dependencies
FROM python:3.11-slim as base
# ... shared setup ...

# Test stage with test dependencies
FROM base as test
# ... test-specific setup ...

# Production stage
FROM base as production
# ... production setup ...
```

### Docker Compose Test Service
```yaml
test:
  build:
    context: .
    target: test
  volumes:
    - ./htmlcov:/app/htmlcov
    - ./tests:/app/tests:ro
  environment:
    - NOTION_INTEGRATION_SECRET=test-token
  profiles: [test]
```

## 🧪 Integration Testing

Integration tests verify the system works with real Notion and OpenAI APIs using test databases.

### Prerequisites
1. **Test Notion Databases**: Create separate test databases in Notion
2. **Test Configuration**: Create `test_notion_config.yaml` with test database IDs
3. **API Tokens**: Store tokens in `.test_token` (Notion) and `.test_token_openai` (OpenAI)

### File Setup
```bash
# Create test configuration
cat > test_notion_config.yaml <<EOF
template_tasks_db_id: "your_test_template_db_id"
active_tasks_db_id: "your_test_active_db_id"
EOF

# Create token files
echo "ntn_your_notion_test_token" > .test_token
echo "sk-your_openai_test_token" > .test_token_openai
```

**Note**: These files are gitignored to prevent committing sensitive credentials.

### Running Integration Tests

Integration tests are in `test_comments_integration.py` and test:
- Comment retrieval from Notion pages
- Comment copying between pages
- OpenAI GPT summarization
- Adding comments to pages

```bash
# Build Docker test image
docker build --target test -t taskmanager-test .

# Run integration tests with test databases
docker run --rm \
  -v "${PWD}:/app" \
  -e NOTION_INTEGRATION_SECRET="$(cat .test_token)" \
  -e OPENAI_API_KEY="$(cat .test_token_openai)" \
  taskmanager-test python test_comments_integration.py
```

### Integration Test Output
```
============================================================
INTEGRATION TESTS FOR COMMENT FUNCTIONALITY
============================================================

TEST 1: Comment Retrieval
✓ Successfully retrieved 0 comments

TEST 2: Comment Copying
✓ Successfully copied 1 comments

TEST 3: Comment Summarization
✓ Successfully generated summary:
[GPT-generated summary appears here]

TEST 4: Adding Comments
✓ Successfully added comment

============================================================
✓ ALL TESTS PASSED
============================================================
```

### Important Notes
- Always use `test_notion_config.yaml` for integration tests (not `notion_config.yaml`)
- Integration tests will write data to Notion (comments)
- Verify you're using test databases before running
- OpenAI API calls will incur costs (minimal for testing)

## 🔄 Continuous Integration

### GitHub Actions Workflow
- **Triggers**: Push to main/develop, pull requests
- **Environment**: Ubuntu latest with Docker
- **Steps**:
  1. Checkout code
  2. Build test Docker image
  3. Run tests in container
  4. Upload coverage reports

**Note**: CI only runs unit tests (mocked), not integration tests.
  5. Generate test summary

### CI/CD Benefits
- **Consistent Environment**: Same Docker image locally and in CI
- **No Secrets Required**: All external dependencies mocked
- **Fast Execution**: Optimized Docker layers and caching
- **Artifact Storage**: Coverage reports saved as artifacts

## 🛠️ Development Workflow

### Adding New Tests
1. Add test functions to `tests/test_daily_planned_date_review.py`
2. Use appropriate pytest markers (`@pytest.mark.unit`, `@pytest.mark.integration`)
3. Mock any external dependencies
4. Run tests locally: `./run_tests_container.sh`

### Test Best Practices
- **Mock External Dependencies**: Never make real API calls in tests
- **Use Descriptive Names**: Test function names should describe the scenario
- **Test Edge Cases**: Include boundary conditions and error scenarios
- **Keep Tests Fast**: Use efficient mocking and avoid unnecessary setup

### Debugging Tests
```bash
# Run with debug output
docker run --rm notion-home-task-manager:test pytest tests/ -v -s

# Run specific failing test
docker run --rm notion-home-task-manager:test pytest tests/ -k "test_name" -v -s

# Enter container for debugging
docker run --rm -it notion-home-task-manager:test /bin/bash
```

## 📈 Performance Testing

### Load Testing
```bash
# Test with large datasets
docker run --rm notion-home-task-manager:test pytest tests/ -m performance

# Monitor resource usage
docker run --rm --memory=512m notion-home-task-manager:test pytest tests/
```

### Performance Criteria
- **Execution Time**: Tests complete within 30 seconds
- **Memory Usage**: <100MB for typical test runs
- **API Rate Limiting**: Respects mocked rate limits

## 🔒 Security Testing

### Authentication Tests
- Invalid API tokens
- Missing permissions
- Expired credentials

### Data Validation
- Malformed task data
- Invalid date formats
- Missing required properties

## 🚨 Troubleshooting

### Common Issues

**Docker not running**
```bash
# Start Docker
sudo systemctl start docker
# or
open -a Docker  # macOS
```

**Permission denied**
```bash
# Make test runner executable
chmod +x run_tests_container.sh
```

**Tests failing due to imports**
- Ensure all external dependencies are properly mocked
- Check that environment variables are mocked before imports

**Coverage reports not generated**
```bash
# Check if htmlcov directory exists
ls -la htmlcov/
# Rebuild test image
docker build --target test -t notion-home-task-manager:test .
```

### Getting Help
1. Check the test output for specific error messages
2. Verify Docker and Docker Compose are running
3. Ensure all test files are properly formatted
4. Review the test plan document for detailed scenarios

## 📚 Additional Resources

- [Test Plan Document](test_plan_daily_planned_date_review.md) - Comprehensive test strategy
- [Pytest Documentation](https://docs.pytest.org/) - Testing framework guide
- [Docker Testing Best Practices](https://docs.docker.com/develop/dev-best-practices/) - Container testing
- [GitHub Actions Documentation](https://docs.github.com/en/actions) - CI/CD workflows

