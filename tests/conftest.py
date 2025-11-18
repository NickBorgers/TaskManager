"""
Shared pytest configuration and fixtures for integration tests.

This module provides rate limiting functionality to prevent hitting Notion API limits
during integration test runs in CI/CD environments.
"""

import time
import pytest
from datetime import datetime, timedelta

# Track API calls globally across all tests
class RateLimiter:
    """
    Global rate limiter for Notion API calls during testing.

    Notion's rate limit: 3 requests/second average, 2700 calls per 15 minutes.
    We'll be conservative and aim for 2 requests/second to account for bursts.
    """
    def __init__(self):
        self.call_times = []
        self.max_calls_per_15_min = 2500  # Conservative limit (actual is 2700)
        self.min_delay_between_calls = 0.5  # 2 requests/second
        self.last_call_time = None

    def wait_if_needed(self):
        """Wait if we're approaching rate limits."""
        current_time = time.time()

        # Remove calls older than 15 minutes
        cutoff_time = current_time - (15 * 60)
        self.call_times = [t for t in self.call_times if t > cutoff_time]

        # Check if we're near the 15-minute limit
        if len(self.call_times) >= self.max_calls_per_15_min * 0.9:  # 90% threshold
            # Wait for the oldest call to age out
            if self.call_times:
                oldest_call = self.call_times[0]
                wait_time = (oldest_call + (15 * 60) + 1) - current_time
                if wait_time > 0:
                    print(f"\nApproaching rate limit ({len(self.call_times)} calls in 15 min). "
                          f"Waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    current_time = time.time()

        # Enforce minimum delay between calls
        if self.last_call_time:
            time_since_last_call = current_time - self.last_call_time
            if time_since_last_call < self.min_delay_between_calls:
                wait_time = self.min_delay_between_calls - time_since_last_call
                time.sleep(wait_time)
                current_time = time.time()

        # Record this call
        self.call_times.append(current_time)
        self.last_call_time = current_time

    def register_bulk_calls(self, count):
        """Register multiple API calls at once (e.g., from script execution)."""
        current_time = time.time()
        for i in range(count):
            self.call_times.append(current_time)
        self.last_call_time = current_time


# Global rate limiter instance
_rate_limiter = RateLimiter()


@pytest.fixture(scope="function", autouse=True)
def rate_limit_integration_tests(request):
    """
    Automatically rate limit all integration tests.

    This fixture runs before each test function and ensures we don't
    exceed Notion's API rate limits. It's marked as autouse=True so it
    applies to all tests automatically.
    """
    # Only apply to integration tests (files starting with test_integration_)
    if "integration" in request.node.fspath.basename:
        _rate_limiter.wait_if_needed()
        yield
        # Add a small delay after each integration test to space them out
        time.sleep(1.0)
    else:
        yield


@pytest.fixture(scope="function")
def rate_limited_script_runner():
    """
    Fixture that wraps subprocess script execution with rate limiting.

    Use this instead of directly calling subprocess.run() in integration tests
    to ensure proper rate limiting between script executions.
    """
    import subprocess
    import os

    def run_script(script_args, estimate_api_calls=50):
        """
        Run a script with rate limiting.

        Args:
            script_args: List of arguments for subprocess.run()
            estimate_api_calls: Estimated number of API calls the script will make

        Returns:
            subprocess.CompletedProcess result
        """
        # Wait for rate limiting before script execution
        _rate_limiter.wait_if_needed()

        # Run the script
        result = subprocess.run(
            script_args,
            capture_output=True,
            text=True,
            env={**os.environ, "NOTION_INTEGRATION_SECRET": os.environ.get("NOTION_INTEGRATION_SECRET")}
        )

        # Register the estimated API calls
        _rate_limiter.register_bulk_calls(estimate_api_calls)

        # Add a delay after script execution to let rate limits recover
        time.sleep(2.0)

        return result

    return run_script


@pytest.fixture(scope="function")
def rate_limited_notion_query():
    """
    Fixture that wraps Notion client queries with rate limiting.

    Use this to wrap individual notion_client database queries in integration tests.
    """
    def query_with_limit(notion_client, method, *args, **kwargs):
        """
        Execute a Notion client method with rate limiting.

        Args:
            notion_client: The Notion client instance
            method: Method name to call (e.g., 'databases.query')
            *args, **kwargs: Arguments to pass to the method

        Returns:
            Result from the method call
        """
        _rate_limiter.wait_if_needed()

        # Navigate to the method (e.g., "databases.query" -> client.databases.query)
        obj = notion_client
        for part in method.split('.'):
            obj = getattr(obj, part)

        result = obj(*args, **kwargs)
        _rate_limiter.register_bulk_calls(1)

        return result

    return query_with_limit
