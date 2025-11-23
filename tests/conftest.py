"""
Shared pytest configuration and fixtures for integration tests.
"""

import os
import subprocess
import pytest


@pytest.fixture(scope="function")
def script_runner():
    """
    Fixture that wraps subprocess script execution for integration tests.

    Rate limiting is handled by the Notion client itself via
    utils/notion_client.py's proactive rate limiter.
    """

    def run_script(script_args):
        """
        Run a script as a subprocess.

        Args:
            script_args: List of arguments for subprocess.run()

        Returns:
            subprocess.CompletedProcess result
        """
        result = subprocess.run(
            script_args,
            capture_output=True,
            text=True,
            env={**os.environ, "NOTION_INTEGRATION_SECRET": os.environ.get("NOTION_INTEGRATION_SECRET")}
        )
        return result

    return run_script


# Alias for backwards compatibility with existing tests
@pytest.fixture(scope="function")
def rate_limited_script_runner(script_runner):
    """
    Backwards-compatible alias for script_runner.

    Rate limiting is now handled by utils/notion_client.py,
    so this is just a simple script runner.
    """
    def run_script(script_args, estimate_api_calls=None):
        # estimate_api_calls is ignored - kept for signature compatibility
        return script_runner(script_args)

    return run_script
