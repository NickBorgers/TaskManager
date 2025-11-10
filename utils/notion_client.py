"""
Rate-limited Notion client wrapper with retry logic.

This module provides a wrapper around the Notion client that handles:
- Rate limiting (429 errors) with exponential backoff
- Automatic retries for transient failures
- Consistent error handling
"""

import time
import logging
from functools import wraps
from typing import Any, Callable
from notion_client import Client
from notion_client.errors import APIResponseError

logger = logging.getLogger(__name__)

# Configuration
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 1.0  # seconds
MAX_RETRY_DELAY = 60.0  # seconds
BACKOFF_MULTIPLIER = 2.0


def with_retry(func: Callable) -> Callable:
    """
    Decorator that adds retry logic with exponential backoff for rate-limited API calls.

    Handles 429 (rate limit) errors by waiting and retrying with exponential backoff.
    """
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        retries = 0
        delay = INITIAL_RETRY_DELAY

        while retries < MAX_RETRIES:
            try:
                return func(*args, **kwargs)
            except APIResponseError as e:
                # Check if this is a rate limit error
                if e.code == "rate_limited" or (hasattr(e, 'status') and e.status == 429):
                    retries += 1
                    if retries >= MAX_RETRIES:
                        logger.error(f"Max retries ({MAX_RETRIES}) exceeded for {func.__name__}")
                        raise

                    wait_time = min(delay, MAX_RETRY_DELAY)
                    logger.warning(
                        f"Rate limited on {func.__name__}. "
                        f"Retry {retries}/{MAX_RETRIES} after {wait_time:.1f}s"
                    )
                    time.sleep(wait_time)
                    delay *= BACKOFF_MULTIPLIER
                else:
                    # Not a rate limit error, re-raise immediately
                    raise
            except Exception as e:
                # Unexpected error, re-raise
                logger.error(f"Unexpected error in {func.__name__}: {e}")
                raise

        # Should not reach here, but just in case
        raise Exception(f"Failed after {MAX_RETRIES} retries")

    return wrapper


class RateLimitedNotionClient:
    """
    Wrapper around the Notion Client that adds rate limiting and retry logic.

    This wrapper intercepts all API calls and wraps them with retry logic
    to handle rate limiting gracefully.
    """

    def __init__(self, auth: str, **kwargs):
        """
        Initialize the rate-limited Notion client.

        Args:
            auth: Notion API token
            **kwargs: Additional arguments passed to the Notion Client
        """
        self._client = Client(auth=auth, **kwargs)
        self._wrap_client_methods()

    def _wrap_client_methods(self):
        """Wrap all client API endpoint methods with retry logic."""
        # Wrap the main API endpoint objects
        for attr_name in ['databases', 'pages', 'blocks', 'users', 'search', 'comments']:
            if hasattr(self._client, attr_name):
                endpoint = getattr(self._client, attr_name)
                setattr(self, attr_name, self._wrap_endpoint(endpoint))

    def _wrap_endpoint(self, endpoint: Any) -> Any:
        """Create a wrapper object that adds retry logic to all endpoint methods."""
        class WrappedEndpoint:
            def __init__(self, original_endpoint):
                self._original = original_endpoint

            def __getattr__(self, name):
                attr = getattr(self._original, name)
                if callable(attr):
                    return with_retry(attr)
                return attr

        return WrappedEndpoint(endpoint)

    def __getattr__(self, name):
        """Forward any other attributes to the underlying client."""
        return getattr(self._client, name)


def create_rate_limited_client(auth: str, **kwargs) -> RateLimitedNotionClient:
    """
    Factory function to create a rate-limited Notion client.

    Args:
        auth: Notion API token
        **kwargs: Additional arguments passed to the Notion Client

    Returns:
        RateLimitedNotionClient instance
    """
    return RateLimitedNotionClient(auth=auth, **kwargs)
