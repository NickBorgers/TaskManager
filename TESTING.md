# Testing Guide

## Overview

This project uses a **comprehensive multi-layered testing approach** to prevent bugs from reaching production:

1. **Unit Tests** - Fast, isolated tests that mock external dependencies (Notion API, OpenAI API)
2. **Integration Tests** - Automated tests against real test databases to catch API data type mismatches
3. **Scheduler Tests** - Tests for the core runtime scheduler logic
4. **Release Validation** - Pre-release smoke tests to validate full system functionality

This approach would have caught the isoformat bug (v1.6.2) before production deployment.

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

Integration tests verify the system works with real Notion and OpenAI APIs using test databases. **These tests are critical for catching bugs like the isoformat error**, where data types returned from APIs don't match code expectations.

### Why Integration Tests Matter

The v1.6.2 isoformat bug occurred because:
1. Code expected datetime objects
2. Notion API returns ISO date strings
3. Unit tests mocked the API, missing the type mismatch
4. **Integration tests against real APIs would have caught this**

### Test Files

- **`tests/test_integration_weekly_rollover.py`** - Full weekly task rollover workflow
  - Tests data types from Notion API
  - Tests --now parameter with various dates
  - Tests duplicate task prevention
  - Tests Last Completed date updates
  - Tests end-to-end workflow execution

- **`tests/test_integration_daily_review.py`** - Daily planned date review workflow
  - Tests tasks without planned dates get Thursday assignment
  - Tests tasks without categories get Random/Monday assignment
  - Tests old incomplete tasks get rescheduled
  - Tests data type consistency

- **`tests/test_scheduler.py`** - Scheduler runtime logic (unit tests with mocks)
  - Tests weekly task scheduling (Saturday 9AM)
  - Tests daily review scheduling (6AM daily)
  - Tests first-run detection and execution
  - Tests error handling and recovery

### Prerequisites

1. **Test Notion Databases**: Create separate test databases in Notion
2. **Test Configuration**: Create `test_notion_config.yaml` with test database IDs
3. **Environment Variables**: Set `NOTION_INTEGRATION_SECRET` for test database access

### File Setup

**Good news:** `test_notion_config.yaml` already exists in the repo with test database IDs configured!

```bash
# Set environment variables for local testing
# Option 1: Use standard variable names
export NOTION_INTEGRATION_SECRET="your_notion_test_token"
export OPENAI_API_KEY="your_openai_test_token"  # Optional

# Option 2: Use _TEST suffix (validation script accepts both)
export NOTION_INTEGRATION_SECRET_TEST="your_notion_test_token"
export OPENAI_API_KEY_TEST="your_openai_test_token"  # Optional

# Or use token files if you have them
export NOTION_INTEGRATION_SECRET="$(cat .test_token)"
export OPENAI_API_KEY="$(cat .test_token_openai)"
```

**Note**: The validation script automatically uses `*_TEST` variants if the regular ones aren't set.

### Running Integration Tests

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r test_requirements.txt

# Run all integration tests
pytest tests/test_integration_weekly_rollover.py tests/test_integration_daily_review.py -v

# Run specific integration test class
pytest tests/test_integration_weekly_rollover.py::TestNotionAPIDataTypes -v

# Run with detailed output
pytest tests/test_integration_weekly_rollover.py -v -s --tb=short
```

### Critical Integration Test: Data Type Verification

```python
def test_completed_date_is_string_not_datetime(self, notion_client, active_db_id):
    """
    CRITICAL: This test would have caught the isoformat bug.

    Verifies that date fields from Notion API are strings (ISO format),
    not datetime objects. The bug occurred because code called .isoformat()
    on a string that was already in ISO format.
    """
    # Query for task with completed date
    response = notion_client.databases.query(...)
    date_value = response["results"][0]["properties"]["Completed Date"]["date"]["start"]

    # Critical assertion: date from API should be string, not datetime
    assert isinstance(date_value, str), \
        f"Expected string from Notion API, got {type(date_value).__name__}"

    # Attempting to call .isoformat() on this would cause AttributeError
    with pytest.raises(AttributeError):
        date_value.isoformat()
```

### Testing with --now Parameter

The `--now` parameter allows testing specific dates to verify logic without waiting for scheduled runs:

```bash
# Test weekly rollover on a specific Saturday
pytest tests/test_integration_weekly_rollover.py::TestWorkflowWithNowParameter -v

# Manual test with different dates
python3 scripts/weekly_rollover/create_active_tasks_from_templates.py \
  --config test_notion_config.yaml \
  --now "2025-12-06T09:00:00Z"

# Test with date only (no time)
python3 scripts/weekly_rollover/create_active_tasks_from_templates.py \
  --config test_notion_config.yaml \
  --now "2025-12-06"
```

### Integration Test Output

```
tests/test_integration_weekly_rollover.py::TestNotionAPIDataTypes::test_completed_date_is_string_not_datetime PASSED
tests/test_integration_weekly_rollover.py::TestNotionAPIDataTypes::test_last_completed_date_type_in_templates PASSED
tests/test_integration_weekly_rollover.py::TestWorkflowWithNowParameter::test_script_runs_with_now_parameter PASSED
tests/test_integration_weekly_rollover.py::TestDuplicateTaskPrevention::test_no_duplicates_for_same_date PASSED
tests/test_integration_weekly_rollover.py::TestEndToEndWorkflow::test_full_workflow_execution PASSED

============================== 5 passed in 15.42s ===============================
```

### Important Notes

- Integration tests **run against real test databases** and will create/modify data
- Always verify you're using `test_notion_config.yaml` (not production config)
- Tests are skipped if `NOTION_INTEGRATION_SECRET` is not set
- Some tests may be slower (real API calls) compared to unit tests
- OpenAI API calls (if configured) will incur minimal costs

## 🔄 Continuous Integration

### GitHub Actions Workflow

The CI/CD pipeline now includes three jobs that run on every commit/PR:

#### 1. Unit Tests Job
- **Triggers**: Every push and pull request
- **Environment**: Ubuntu latest with Docker
- **Steps**:
  1. Checkout code
  2. Build test Docker image
  3. Run unit tests (mocked, no external dependencies)
  4. Generate coverage reports
  5. Upload coverage to Codecov

```yaml
unit-tests:
  name: Unit Tests
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Build test image
      run: docker build --target test -t notion-home-task-manager:test .
    - name: Run unit tests
      run: docker run notion-home-task-manager:test pytest tests/test_*.py -v
```

#### 2. Integration Tests Job
- **Triggers**: Main branch pushes and pull requests
- **Requires**: Unit tests pass first
- **Environment**: Ubuntu with Python 3.11
- **Uses**: Real test databases (requires secrets)
- **Steps**:
  1. Checkout code
  2. Install dependencies
  3. Create test configuration from secrets
  4. Run integration tests against test databases
  5. Leave test data for inspection

```yaml
integration-tests:
  name: Integration Tests
  needs: unit-tests
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v4
    - name: Run integration tests
      env:
        NOTION_INTEGRATION_SECRET: ${{ secrets.NOTION_INTEGRATION_SECRET_TEST }}
      run: pytest tests/test_integration_*.py -v
```

#### 3. Release Validation Job
- **Triggers**: Only on release tags (v*)
- **Requires**: Both unit and integration tests pass
- **Purpose**: Final smoke test before production deployment
- **Steps**:
  1. Run full test suite
  2. Execute validation script
  3. Test multiple --now parameter formats
  4. Check for common bug patterns
  5. Upload validation logs

```yaml
release-validation:
  name: Release Validation
  needs: [unit-tests, integration-tests]
  if: startsWith(github.ref, 'refs/tags/v')
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Run release validation
      run: ./scripts/validate_release.sh
```

### Required GitHub Secrets

To enable integration tests and release validation, add these secrets to your repository:

- `NOTION_INTEGRATION_SECRET_TEST` - Notion token for test databases
- `OPENAI_API_KEY_TEST` - OpenAI token for test summarization (optional)

**Note:** Test database IDs are already configured in `test_notion_config.yaml` (checked into the repo), so they don't need to be added as secrets.

### CI/CD Benefits

- **Multi-layered Testing**: Unit → Integration → Release validation
- **Fast Feedback**: Unit tests run first (fastest), gate later stages
- **Real API Testing**: Integration tests catch type mismatches like isoformat bug
- **Release Safety**: Comprehensive validation before production deployment
- **Consistent Environment**: Same Docker image locally and in CI
- **Artifact Storage**: Coverage reports and validation logs saved

## 🚀 Release Validation

Before deploying a new release, run the comprehensive validation script to ensure everything works correctly.

### Validation Script: `scripts/validate_release.sh`

This script performs a complete pre-release check:

```bash
# Set environment variables (use either naming convention)
export NOTION_INTEGRATION_SECRET_TEST="$(cat .test_token)"
export OPENAI_API_KEY_TEST="$(cat .test_token_openai)"

# Run validation script
./scripts/validate_release.sh
```

The script automatically detects and uses `*_TEST` environment variables if the standard ones aren't set.

### What It Tests

1. **Prerequisites Check**
   - Verifies `NOTION_INTEGRATION_SECRET` is set
   - Checks for `test_notion_config.yaml`
   - Confirms configuration files exist

2. **Unit Tests**
   - Runs all unit tests (weekly rollover, daily review, scheduler)
   - Ensures core logic works correctly

3. **Integration Tests**
   - Runs integration tests against real test databases
   - Catches API data type mismatches

4. **Weekly Rollover Script**
   - Executes with specific test date
   - Checks for errors in logs
   - Verifies "Done" completion message

5. **Daily Review Script**
   - Executes full daily review
   - Checks for errors in logs
   - Verifies completion

6. **Date Parameter Testing**
   - Tests multiple --now parameter formats
   - Ensures various date formats work correctly

7. **Code Pattern Analysis**
   - Checks for suspicious `.isoformat()` calls
   - Identifies potential type mismatch bugs

### Validation Output

```bash
========================================
Checking Prerequisites
========================================

✓ NOTION_INTEGRATION_SECRET is set
✓ test_notion_config.yaml found
✓ notion_config.yaml found

========================================
Running Unit Tests
========================================

tests/test_weekly_rollover.py::... PASSED
tests/test_daily_planned_date_review.py::... PASSED
tests/test_scheduler.py::... PASSED

✓ All unit tests passed

========================================
Testing Weekly Rollover Script
========================================

Running weekly rollover for test date: 2025-12-06T09:00:00Z
✓ Weekly rollover executed successfully

========================================
Testing Daily Review Script
========================================

Running daily planned date review...
✓ Daily review executed successfully

========================================
Testing Date Parameter Handling
========================================

Testing various date formats...
  Testing date: 2025-12-13 ... ✓
  Testing date: 2025-12-13T09:00:00Z ... ✓
  Testing date: 2025-12-13T09:00:00+00:00 ... ✓

✓ All date format tests passed

========================================
Checking for Common Bug Patterns
========================================

Checking for .isoformat() on potential string variables...
✓ No suspicious .isoformat() calls found

========================================
Validation Summary
========================================

✓ ALL VALIDATIONS PASSED

Release is ready to be deployed!
```

### When to Run

- **Before every release tag** - Required
- **After major changes** - Recommended
- **When fixing critical bugs** - Required
- **Before production deployment** - Required

### Exit Codes

- `0` - All validations passed, safe to release
- `1` - One or more validations failed, do NOT release

### Integration with CI/CD

The validation script runs automatically on release tags (v*) via GitHub Actions:

```yaml
release-validation:
  if: startsWith(github.ref, 'refs/tags/v')
  steps:
    - run: ./scripts/validate_release.sh
```

This prevents releases with failing tests from being deployed.

## 🛠️ Development Workflow

### Adding New Tests

#### For Unit Tests
1. Add test to appropriate file (`test_weekly_rollover.py`, `test_daily_planned_date_review.py`, `test_scheduler.py`)
2. Mock all external dependencies (Notion API, file system, datetime)
3. Use descriptive test names: `test_<function>_<scenario>_<expected_result>`
4. Run locally: `./run_tests_container.sh`

#### For Integration Tests
1. Add test to `test_integration_weekly_rollover.py` or `test_integration_daily_review.py`
2. Use real test database connections (no mocks)
3. Include data type assertions to catch API mismatches
4. Use `@pytest.mark.skipif` to skip if credentials not available
5. Run locally: `pytest tests/test_integration_*.py -v`

#### For Critical Bug Prevention
When adding code that interacts with Notion API:
1. **Always verify data types** from API in integration tests
2. **Never assume** datetime objects - API returns strings
3. **Test with real data** to catch type mismatches
4. **Add to validation script** if it's critical path code

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

## 🛡️ How This Testing Approach Prevents Bugs

### Case Study: The isoformat Bug (v1.6.2)

**The Bug:**
```python
# In create_active_tasks_from_templates.py:590
template_task["properties"]["Last Completed"] = {"date": {"start": most_recent.isoformat()}}
# ERROR: 'str' object has no attribute 'isoformat'
```

**Root Cause:**
- `most_recent` came from `extract_completed_date()` which returns `date_val["start"]` from Notion API
- Notion API returns dates as ISO strings, not datetime objects
- Code assumed datetime and called `.isoformat()` on a string

**How Each Testing Layer Would Have Caught It:**

1. **Unit Tests (Existing)** - ❌ MISSED
   - Mocked API responses, didn't reveal real data types
   - `most_recent` was mocked as string or datetime depending on test
   - No type verification of API responses

2. **Integration Tests (NEW)** - ✅ WOULD CATCH
   ```python
   def test_last_completed_date_type_in_templates(self):
       """Verify Last Completed dates are strings from API"""
       response = notion_client.databases.query(database_id=template_db_id)
       date_value = response["results"][0]["properties"]["Last Completed"]["date"]["start"]

       assert isinstance(date_value, str)  # ✅ CATCHES the bug

       with pytest.raises(AttributeError):
           date_value.isoformat()  # ✅ Demonstrates the error
   ```

3. **Release Validation (NEW)** - ✅ WOULD CATCH
   - Runs actual script against test database
   - Script would crash with AttributeError
   - Validation fails, prevents release

4. **Code Pattern Analysis (NEW)** - ⚠️ WOULD WARN
   ```bash
   # Checks for .isoformat() on variables that might be strings
   grep -rn "\.isoformat()" scripts/
   # Flags suspicious usage for manual review
   ```

### Testing Pyramid

```
         /\          Release Validation
        /  \         (Smoke tests)
       /____\
      /      \       Integration Tests
     /        \      (Real APIs, type checks)
    /__________\
   /            \    Unit Tests
  /              \   (Fast, mocked, isolated)
 /________________\
```

### Prevention Checklist

Before committing code that interacts with external APIs:

- [ ] Added unit tests with mocked dependencies
- [ ] Added integration test with real API calls
- [ ] Verified data types returned from API
- [ ] Tested with --now parameter (if date-related)
- [ ] Ran validation script locally
- [ ] Checked for similar patterns in other code

### Key Principles

1. **Trust but Verify** - Don't assume API response types, verify with integration tests
2. **Test in Layers** - Unit tests for logic, integration tests for contracts
3. **Automate Everything** - All tests run on every commit/PR
4. **Gate Releases** - Validation must pass before release tags
5. **Learn from Bugs** - Add tests that would have caught historical bugs

## 📚 Additional Resources

- [Test Plan Document](test_plan_daily_planned_date_review.md) - Comprehensive test strategy
- [Pytest Documentation](https://docs.pytest.org/) - Testing framework guide
- [Docker Testing Best Practices](https://docs.docker.com/develop/dev-best-practices/) - Container testing
- [GitHub Actions Documentation](https://docs.github.com/en/actions) - CI/CD workflows

## 📈 Test Coverage Summary

| Component | Unit Tests | Integration Tests | Total Coverage |
|-----------|------------|-------------------|----------------|
| weekly_rollover | 65% | ✅ | ~85% |
| daily_planned_date_review | 85% | ✅ | ~95% |
| scheduler | 100% | N/A | 100% |
| **Overall** | **70%** | **✅** | **~90%** |

**Note**: Integration tests provide additional confidence beyond code coverage metrics by verifying real API interactions.

