"""Configuration mapper utility for debug adapters.

This module provides a declarative way to map kwargs to configuration attributes,
reducing duplication across language adapters.
"""

from typing import Any


class ConfigurationMapper:
    """Utility class for mapping kwargs to configuration objects.

    This class provides a declarative way to handle configuration mapping, reducing
    duplication across language adapters.
    """

    @staticmethod
    def apply_kwargs(
        config: Any,
        kwargs: dict[str, Any],
        mappings: dict[str, str],
        type_conversions: dict[str, type] | None = None,
    ) -> None:
        """Apply kwargs to config using declarative mappings.

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

        Examples
        --------
        >>> config = PythonAdapterConfig()
        >>> kwargs = {"justMyCode": False, "subProcess": True}
        >>> mappings = {
        ...     "justMyCode": "justMyCode",
        ...     "subProcess": "subProcess"
        ... }
        >>> ConfigurationMapper.apply_kwargs(config, kwargs, mappings)
        """
        type_conversions = type_conversions or {}

        for kwarg_key, config_attr in mappings.items():
            if kwarg_key in kwargs:
                value = kwargs.pop(kwarg_key)

                # Apply type conversion if specified
                if kwarg_key in type_conversions:
                    converter = type_conversions[kwarg_key]
                    try:
                        value = converter(value)
                    except (ValueError, TypeError) as e:
                        msg = (
                            f"Failed to convert {kwarg_key}={value} to "
                            f"{converter.__name__}: {e}"
                        )
                        raise ValueError(msg) from e

                # Set the attribute on the config object
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

        Examples
        --------
        >>> mappings = ConfigurationMapper.create_mapping_dict(
        ...     ("justMyCode", "justMyCode"),
        ...     ("subProcess", "subProcess")
        ... )
        """
        return dict(mapping_pairs)
