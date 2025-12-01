"""Mock configuration mapper for unit tests.

Provides mock implementations of ConfigurationMapper for testing configuration handling
in adapters.
"""

from typing import Any
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_config_mapper() -> MagicMock:
    """Create a mock ConfigurationMapper.

    The mock simulates ConfigurationMapper for testing
    configuration mapping without side effects.

    Returns
    -------
    MagicMock
        Mock configuration mapper with static methods
    """
    mapper = MagicMock()

    # Static methods
    mapper.apply_kwargs = MagicMock()
    mapper.create_mapping_dict = MagicMock(return_value={})

    return mapper


class MockConfigurationMapper:
    """Configuration mapper mock with tracking.

    Use this when you need to verify configuration mapping.

    Examples
    --------
    >>> mapper = MockConfigurationMapper()
    >>> mapper.apply_kwargs(config, kwargs, mappings)
    >>> assert len(mapper.apply_calls) == 1
    """

    def __init__(self) -> None:
        """Initialize the mock mapper."""
        self.apply_calls: list[dict[str, Any]] = []
        self.mapping_calls: list[tuple[tuple, ...]] = []

    @staticmethod
    def apply_kwargs(
        config: Any,
        kwargs: dict[str, Any],
        mappings: dict[str, str],
        type_conversions: dict[str, type] | None = None,
    ) -> None:
        """Apply kwargs to config using mappings.

        This mock implementation actually applies the mappings
        for functional testing.

        Parameters
        ----------
        config : Any
            Configuration object to update
        kwargs : Dict[str, Any]
            Keyword arguments to process
        mappings : Dict[str, str]
            Mapping from kwarg key to config attribute name
        type_conversions : Dict[str, type], optional
            Optional type conversions for specific keys
        """
        type_conversions = type_conversions or {}

        for kwarg_key, config_attr in mappings.items():
            if kwarg_key in kwargs:
                value = kwargs.pop(kwarg_key)

                if kwarg_key in type_conversions:
                    converter = type_conversions[kwarg_key]
                    value = converter(value)

                setattr(config, config_attr, value)

    @staticmethod
    def create_mapping_dict(*mapping_pairs: tuple) -> dict[str, str]:
        """Create mapping dictionaries from pairs.

        Parameters
        ----------
        *mapping_pairs : tuple
            Variable number of (kwarg_key, config_attr) pairs

        Returns
        -------
        Dict[str, str]
            Mapping dictionary
        """
        return dict(mapping_pairs)


class TrackingConfigurationMapper:
    """Configuration mapper that tracks all operations.

    Use this when you need to verify which mappings were applied
    without actually modifying the config object.

    Examples
    --------
    >>> mapper = TrackingConfigurationMapper()
    >>> mapper.apply_kwargs(config, {"debug": True}, {"debug": "debug_mode"})
    >>> assert mapper.apply_calls[0]["kwargs"] == {"debug": True}
    """

    def __init__(self) -> None:
        """Initialize the tracking mapper."""
        self.apply_calls: list[dict[str, Any]] = []
        self.mapping_calls: list[tuple[tuple, ...]] = []

    def apply_kwargs(
        self,
        config: Any,
        kwargs: dict[str, Any],
        mappings: dict[str, str],
        type_conversions: dict[str, type] | None = None,
    ) -> None:
        """Track apply_kwargs calls without modifying config.

        Parameters
        ----------
        config : Any
            Configuration object (not modified)
        kwargs : Dict[str, Any]
            Keyword arguments
        mappings : Dict[str, str]
            Mapping dict
        type_conversions : Dict[str, type], optional
            Type conversions
        """
        self.apply_calls.append(
            {
                "config": config,
                "kwargs": kwargs.copy(),
                "mappings": mappings.copy(),
                "type_conversions": type_conversions,
            }
        )

    def create_mapping_dict(self, *mapping_pairs: tuple) -> dict[str, str]:
        """Track create_mapping_dict calls.

        Parameters
        ----------
        *mapping_pairs : tuple
            Mapping pairs

        Returns
        -------
        Dict[str, str]
            Mapping dictionary
        """
        self.mapping_calls.append(mapping_pairs)
        return dict(mapping_pairs)

    def reset(self) -> None:
        """Reset tracking state."""
        self.apply_calls.clear()
        self.mapping_calls.clear()


@pytest.fixture
def mock_config_mapper_tracking() -> TrackingConfigurationMapper:
    """Create a configuration mapper that tracks operations.

    Returns
    -------
    TrackingConfigurationMapper
        Mock with operation tracking for verification
    """
    return TrackingConfigurationMapper()


@pytest.fixture
def mock_config_mapper_functional() -> type[MockConfigurationMapper]:
    """Create a functional configuration mapper.

    This mapper actually applies mappings, useful for integration-style
    unit tests.

    Returns
    -------
    Type[MockConfigurationMapper]
        The MockConfigurationMapper class with static methods
    """
    return MockConfigurationMapper
