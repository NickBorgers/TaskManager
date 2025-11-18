# Integration Test Rate Limiting

## Problem

Integration tests were hitting Notion API rate limits during GitHub Actions CI runs, causing test failures with 429 errors.

**Notion API Rate Limits:**
- 3 requests per second (average)
- 2700 calls per 15 minutes
- Bursts are allowed

## Root Cause

The integration tests make many API calls:
- Each script execution (via subprocess) makes 20-50+ API calls
- Tests also make direct database queries (before/after comparisons)
- Some tests run scripts multiple times (e.g., duplicate detection tests)
- All tests run sequentially without delays

This resulted in hundreds of API calls in rapid succession, exceeding Notion's rate limits.

## Solution

Implemented automatic rate limiting via pytest fixtures in `tests/conftest.py`:

### 1. Global Rate Limiter
- Tracks all API calls across tests
- Enforces minimum 0.5s delay between calls (conservative 2 req/sec)
- Prevents exceeding 90% of 15-minute limit (2500/2700 calls)
- Automatically waits if approaching limits

### 2. Auto-Applied Fixture
```python
@pytest.fixture(scope="function", autouse=True)
def rate_limit_integration_tests(request):
```
- Automatically applies to all integration test files
- Adds 1 second delay after each test
- Calls `wait_if_needed()` before each test

### 3. Script Runner Fixture
```python
@pytest.fixture(scope="function")
def rate_limited_script_runner():
```
- Replaces direct `subprocess.run()` calls
- Tracks estimated API calls per script execution
- Adds 2 second delay after script completion
- Allows bursts while respecting overall limits

## Usage

### Before (caused rate limiting):
```python
def test_example(self, test_config):
    import subprocess
    result = subprocess.run(
        ["python3", "script.py"],
        capture_output=True,
        text=True,
        env={...}
    )
```

### After (rate limited):
```python
def test_example(self, test_config, rate_limited_script_runner):
    result = rate_limited_script_runner(
        ["python3", "script.py"],
        estimate_api_calls=50  # Estimate for this script
    )
```

## Configuration

Rate limiting parameters in `tests/conftest.py`:

```python
max_calls_per_15_min = 2500  # Conservative (actual: 2700)
min_delay_between_calls = 0.5  # 2 req/sec (actual: 3 req/sec)
```

These values are intentionally conservative to:
- Account for burst behavior
- Leave headroom for retries in `utils/notion_client.py`
- Prevent edge case race conditions

## Impact

- **Test duration**: Increased by ~2-3 minutes total
- **Reliability**: Eliminates rate limit failures in CI
- **Maintainability**: Automatic - no manual delay management needed

## Related Files

- `tests/conftest.py` - Rate limiting fixtures
- `tests/test_integration_weekly_rollover.py` - Updated to use fixtures
- `tests/test_integration_daily_review.py` - Updated to use fixtures
- `utils/notion_client.py` - Existing retry logic for 429 errors
- `.github/workflows/test.yml` - CI workflow documentation

## Monitoring

If tests still encounter rate limiting:
1. Check GitHub Actions logs for 429 errors
2. Increase delays in `conftest.py`
3. Reduce `estimate_api_calls` values if overestimated
4. Consider splitting integration tests into separate jobs
