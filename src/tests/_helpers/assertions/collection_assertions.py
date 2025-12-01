"""Assertions for collections and sequences.

This module provides assertions for validating lists, dictionaries, and collection
uniqueness.
"""

from collections.abc import Callable
from typing import Any


class CollectionAssertions:
    """Assertions for collections and sequences."""

    @staticmethod
    def assert_list_contains_subset(
        actual_list: list[Any],
        expected_items: list[Any],
        ordered: bool = False,
    ) -> None:
        """Assert that a list contains expected items.

        Parameters
        ----------
        actual_list : List[Any]
            List to check
        expected_items : List[Any]
            Items that should be present
        ordered : bool
            Whether items must appear in order

        Raises
        ------
        AssertionError
            If expected items are not found
        """
        if not ordered:
            for item in expected_items:
                assert item in actual_list, (
                    f"Item {item} not found in list: {actual_list}"
                )
        else:
            actual_iter = iter(actual_list)
            for expected in expected_items:
                found = False
                for actual in actual_iter:
                    if actual == expected:
                        found = True
                        break
                assert found, (
                    f"Ordered item {expected} not found in list: {actual_list}"
                )

    @staticmethod
    def assert_dict_subset(
        actual_dict: dict[str, Any],
        expected_subset: dict[str, Any],
        recursive: bool = True,
    ) -> None:
        """Assert that a dictionary contains expected key-value pairs.

        Parameters
        ----------
        actual_dict : Dict[str, Any]
            Dictionary to check
        expected_subset : Dict[str, Any]
            Expected key-value pairs
        recursive : bool
            Whether to check nested dictionaries

        Raises
        ------
        AssertionError
            If expected pairs are not found
        """
        for key, expected_value in expected_subset.items():
            assert key in actual_dict, f"Key '{key}' not found in dict"

            actual_value = actual_dict[key]

            if (
                recursive
                and isinstance(expected_value, dict)
                and isinstance(actual_value, dict)
            ):
                CollectionAssertions.assert_dict_subset(
                    actual_value,
                    expected_value,
                    recursive,
                )
            else:
                assert actual_value == expected_value, (
                    f"Value mismatch for key '{key}': "
                    f"expected {expected_value}, got {actual_value}"
                )

    @staticmethod
    def assert_unique_items(
        collection: list[Any] | set[Any],
        key_func: Callable[[Any], Any] | None = None,
    ) -> None:
        """Assert that all items in a collection are unique.

        Parameters
        ----------
        collection : Union[List[Any], Set[Any]]
            Collection to check
        key_func : Callable, optional
            Function to extract comparison key from items

        Raises
        ------
        AssertionError
            If duplicate items are found
        """
        if key_func:
            seen_keys = set()
            duplicates = []
            for item in collection:
                key = key_func(item)
                if key in seen_keys:
                    duplicates.append(item)
                seen_keys.add(key)
        else:
            if isinstance(collection, list | tuple):
                unique_items = set(collection)
                duplicates = [
                    item for item in unique_items if collection.count(item) > 1
                ]
            else:
                duplicates = []

        assert not duplicates, f"Duplicate items found: {duplicates}"
