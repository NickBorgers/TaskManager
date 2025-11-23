# Integration Test Rate Limiting

## Problem

Integration tests were hitting Notion API rate limits during GitHub Actions CI runs, causing test failures with 429 errors.

**Notion API Rate Limits:**
- 3 requests per second (average)
- 2700 calls per 15 minutes
- Bursts are allowed

## Solution

Rate limiting is implemented in `utils/notion_client.py` with two layers:

### 1. Proactive Rate Limiting
- Enforces 0.35s delay between API calls (~2.8 req/sec)
- Prevents hitting rate limits before they occur
- Thread-safe for concurrent usage

### 2. Reactive Retry Logic
- Catches 429 errors with exponential backoff
- 5 retries with delays: 1s, 2s, 4s, 8s, 16s (max 60s)
- Fallback if proactive limiting isn't sufficient

## How It Works

```python
# utils/notion_client.py
class ProactiveRateLimiter:
    def wait_if_needed(self):
        # Enforces MIN_DELAY_BETWEEN_CALLS (0.35s) between API calls
        ...

def with_retry(func):
    # Wraps API calls with:
    # 1. Proactive rate limiting (wait before call)
    # 2. Retry logic for 429 errors
    ...
```

All scripts use `create_rate_limited_client()` which automatically applies both layers.

## Configuration

Rate limiting parameters in `utils/notion_client.py`:

```python
MIN_DELAY_BETWEEN_CALLS = 0.35  # ~2.8 req/sec (limit is 3 req/sec)
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 1.0
BACKOFF_MULTIPLIER = 2.0
```

## Impact

- **Test duration**: Scripts run slower due to API call spacing
- **Reliability**: Eliminates rate limit failures in CI
- **Simplicity**: No test-level configuration needed

## Related Files

- `utils/notion_client.py` - Proactive rate limiting and retry logic
- `tests/conftest.py` - Simple script runner fixture for tests
