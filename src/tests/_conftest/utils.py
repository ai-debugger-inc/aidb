"""Utility fixtures for tests.

This module provides general-purpose fixtures like test data paths and benchmarking
utilities.
"""

import time
from pathlib import Path

import pytest


@pytest.fixture
def test_data_dir() -> Path:
    """Provide path to test data directory.

    Returns
    -------
    Path
        Path to test assets directory
    """
    return Path(__file__).parent.parent / "assets"


@pytest.fixture
def benchmark():
    """Provide benchmarking capabilities.

    Returns
    -------
    callable
        Benchmark function
    """

    class Benchmark:
        def __init__(self):
            self.times = []

        def __call__(self, func, *args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            end = time.perf_counter()
            self.times.append(end - start)
            return result

        @property
        def avg(self):
            return sum(self.times) / len(self.times) if self.times else 0

        @property
        def min(self):
            return min(self.times) if self.times else 0

        @property
        def max(self):
            return max(self.times) if self.times else 0

    return Benchmark()
