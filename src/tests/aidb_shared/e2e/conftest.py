"""Pytest configuration and fixtures for E2E tests.

E2E-specific fixtures can be added here. The parent conftest.py
already imports all necessary fixtures from tests._fixtures, including:
- generated_program_factory: Factory for loading generated test programs
- scenario_id: Parametrized fixture for all scenarios
- language: Parametrized fixture for all languages
- docker_test_mode: Boolean indicating if running in Docker
"""

import pytest
