# Test Plan for Daily Planned Date Review Script

## Overview
The `daily_planned_date_review.py` script automates task management in Notion by:
1. Setting planned dates for tasks without them (to next Thursday)
2. Setting categories for tasks without them (to "Random/Monday")
3. Rescheduling old incomplete tasks (to next Thursday)

## Test Environment Setup

### Prerequisites
- Docker and Docker Compose
- No local Python installation required
- No Notion API access required (all external dependencies mocked)
- No environment variables required for testing

### Test Configuration
- Tests run in isolated Docker containers
- All external dependencies (Notion API, config files) are mocked
- No production data access required
- Consistent environment across development and CI/CD

## Test Categories

### 1. Unit Tests

#### 1.1 Configuration and Environment Tests
- **Test**: Environment variable validation
  - **Scenario**: `NOTION_INTEGRATION_SECRET` not set
  - **Expected**: Script raises `EnvironmentError`
  - **Priority**: High

- **Test**: Configuration file validation
  - **Scenario**: Missing or invalid `notion_config.yaml`
  - **Expected**: Script raises `ValueError` for missing `active_tasks_db_id`
  - **Priority**: High

#### 1.2 Date Calculation Tests
- **Test**: `get_thursday_of_next_week()` function
  - **Scenarios**:
    - Today is Monday → should return Thursday of current week
    - Today is Thursday → should return Thursday of next week
    - Today is Friday → should return Thursday of next week
    - Today is Sunday → should return Thursday of current week
  - **Expected**: Correct Thursday date calculation
  - **Priority**: High

#### 1.3 Schema Retrieval Tests
- **Test**: `get_active_schema()` function
  - **Scenario**: Valid database ID
  - **Expected**: Returns database properties
  - **Priority**: Medium

- **Test**: `get_active_schema()` function with invalid database
  - **Scenario**: Invalid database ID
  - **Expected**: Handles API error gracefully
  - **Priority**: Medium

### 2. Integration Tests

#### 2.1 Task Query Tests
- **Test**: `get_active_tasks_without_planned_date()`
  - **Scenarios**:
    - Database with tasks having planned dates
    - Database with tasks without planned dates
    - Database with template tasks (should be excluded)
    - Database with completed tasks (should be excluded)
    - Empty database
  - **Expected**: Correct filtering and exclusion logic
  - **Priority**: High

- **Test**: `get_active_tasks_without_category()`
  - **Scenarios**:
    - Database with tasks having categories
    - Database with tasks without categories
    - Database with template tasks (should be excluded)
    - Database with completed tasks (should be excluded)
  - **Expected**: Correct filtering and exclusion logic
  - **Priority**: High

- **Test**: `get_old_incomplete_tasks()`
  - **Scenarios**:
    - Database with tasks planned for today
    - Database with tasks planned for yesterday
    - Database with tasks planned for last week
    - Database with future planned tasks (should be excluded)
  - **Expected**: Correct date filtering logic
  - **Priority**: High

#### 2.2 Task Update Tests
- **Test**: `update_task_planned_date()`
  - **Scenarios**:
    - Valid task ID and date
    - Invalid task ID
    - Invalid date format
    - API rate limiting
  - **Expected**: Successful updates and error handling
  - **Priority**: High

- **Test**: `update_task_category()`
  - **Scenarios**:
    - Valid task ID and category
    - Invalid task ID
    - Invalid category name
    - API rate limiting
  - **Expected**: Successful updates and error handling
  - **Priority**: High

### 3. End-to-End Tests

#### 3.1 Complete Workflow Tests
- **Test**: Full script execution with mixed task types
  - **Scenario**: Database containing:
    - Tasks without planned dates
    - Tasks without categories
    - Old incomplete tasks
    - Template tasks (should be ignored)
    - Completed tasks (should be ignored)
  - **Expected**: All appropriate tasks updated correctly
  - **Priority**: High

- **Test**: Script execution with no actionable tasks
  - **Scenario**: Database with only template and completed tasks
  - **Expected**: Script completes successfully with no updates
  - **Priority**: Medium

#### 3.2 Error Recovery Tests
- **Test**: Partial failure handling
  - **Scenario**: Some task updates succeed, others fail
  - **Expected**: Script continues processing remaining tasks
  - **Priority**: Medium

- **Test**: Network connectivity issues
  - **Scenario**: Intermittent API connectivity
  - **Expected**: Appropriate retry logic and error logging
  - **Priority**: Medium

### 4. Edge Case Tests

#### 4.1 Data Edge Cases
- **Test**: Tasks with malformed data
  - **Scenario**: Tasks with missing properties or invalid data types
  - **Expected**: Graceful handling and logging
  - **Priority**: Medium

- **Test**: Large database pagination
  - **Scenario**: Database with >100 tasks (requires pagination)
  - **Expected**: All tasks processed correctly
  - **Priority**: Medium

#### 4.2 Date Edge Cases
- **Test**: Year boundary scenarios
  - **Scenario**: Script run on December 31st
  - **Expected**: Correct Thursday calculation across year boundary
  - **Priority**: Low

- **Test**: Leap year scenarios
  - **Scenario**: Script run during leap year
  - **Expected**: Correct date calculations
  - **Priority**: Low

#### 4.3 Status Filtering Edge Cases
- **Test**: Custom status configurations
  - **Scenario**: Database with custom status groups
  - **Expected**: Correct identification of non-complete statuses
  - **Priority**: Medium

- **Test**: Missing status property
  - **Scenario**: Database without status property
  - **Expected**: Script handles gracefully
  - **Priority**: Medium

### 5. Performance Tests

#### 5.1 Load Testing
- **Test**: Large dataset processing
  - **Scenario**: Database with 1000+ tasks
  - **Expected**: Script completes within reasonable time
  - **Priority**: Medium

- **Test**: API rate limiting
  - **Scenario**: Rapid successive executions
  - **Expected**: Respects API rate limits
  - **Priority**: Medium

### 6. Security Tests

#### 6.1 Authentication Tests
- **Test**: Invalid API token
  - **Scenario**: Expired or invalid `NOTION_INTEGRATION_SECRET`
  - **Expected**: Clear error message and graceful failure
  - **Priority**: High

- **Test**: Token permissions
  - **Scenario**: Token without required database access
  - **Expected**: Clear error message about permissions
  - **Priority**: High

## Test Implementation Strategy

### Mock Strategy
- Use `unittest.mock` to mock Notion API calls
- Create mock responses that simulate various database states
- Mock datetime functions for consistent date-based testing
- Mock environment variables and config file loading

### Test Data Management
- Create test fixtures with known task configurations
- All external dependencies mocked - no real database access
- No cleanup procedures needed (isolated containers)

### Continuous Integration
- Run unit tests on every commit via GitHub Actions
- Run integration tests on pull requests
- Run full end-to-end tests nightly
- Containerized testing ensures consistent environment

## Test Execution Plan

### Phase 1: Unit Tests (Week 1)
- Implement configuration and environment tests
- Implement date calculation tests
- Implement schema retrieval tests

### Phase 2: Integration Tests (Week 2)
- Implement task query tests
- Implement task update tests
- Set up test database with sample data

### Phase 3: End-to-End Tests (Week 3)
- Implement complete workflow tests
- Implement error recovery tests
- Test with real Notion API (staging environment)

### Phase 4: Edge Cases and Performance (Week 4)
- Implement edge case tests
- Implement performance tests
- Implement security tests

## Success Criteria

### Functional Criteria
- All unit tests pass with >90% code coverage
- All integration tests pass
- All end-to-end tests pass
- Script handles all error scenarios gracefully

### Performance Criteria
- Script completes within 30 seconds for typical datasets
- Script respects Notion API rate limits
- Memory usage remains reasonable (<100MB)

### Quality Criteria
- Clear error messages for all failure scenarios
- Comprehensive logging for debugging
- No data corruption or unintended side effects

## Risk Mitigation

### High-Risk Scenarios
- **Risk**: Script modifies production data incorrectly
  - **Mitigation**: Use test databases, implement dry-run mode
- **Risk**: API rate limiting causing failures
  - **Mitigation**: Implement exponential backoff and retry logic
- **Risk**: Date calculation errors across timezones
  - **Mitigation**: Use UTC consistently, test timezone edge cases

### Medium-Risk Scenarios
- **Risk**: Large datasets causing timeouts
  - **Mitigation**: Implement pagination and progress logging
- **Risk**: Malformed data causing crashes
  - **Mitigation**: Implement robust error handling and validation

## Test Tools and Frameworks

### Recommended Tools
- **Testing Framework**: `pytest`
- **Mocking**: `unittest.mock` or `pytest-mock`
- **Coverage**: `pytest-cov`
- **API Testing**: `responses` library for mocking HTTP requests
- **Date Testing**: `freezegun` for time-based testing
- **Containerization**: Docker and Docker Compose
- **CI/CD**: GitHub Actions

### Test Structure
```
tests/
├── test_daily_planned_date_review.py  # Main test file
├── fixtures/                          # Test data fixtures
│   ├── sample_tasks.json
│   └── mock_responses.py
└── conftest.py                        # Pytest configuration

Docker/
├── Dockerfile                         # Multi-stage with test target
├── docker-compose.yml                 # Test service configuration
└── run_tests_container.sh             # Containerized test runner

CI/CD/
└── .github/workflows/test.yml         # GitHub Actions workflow
```

This test plan ensures comprehensive coverage of the script's functionality while maintaining code quality and reliability.
