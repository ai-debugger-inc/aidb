"""AIDB Adapter Build System.

A modular system for building debug adapters for various languages.
"""

from .base import AdapterBuilder
from .registry import get_builder, ADAPTER_BUILDERS

__all__ = ["AdapterBuilder", "get_builder", "ADAPTER_BUILDERS"]