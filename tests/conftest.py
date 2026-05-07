"""Shared pytest fixtures and configuration for PlaceGuard tests."""

import os
import sys
import pytest

# Add src to path so tests can import agent modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Set dummy environment variables for unit tests that don't call the LLM."""
    if not os.getenv("OPENAI_API_KEY"):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-dummy-key-for-unit-tests")
    if not os.getenv("ANTHROPIC_API_KEY"):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-test-dummy-key")

