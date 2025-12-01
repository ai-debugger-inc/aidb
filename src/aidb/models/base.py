"""Base class and mixins for response models."""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from aidb.common.errors import AidbError


@dataclass(frozen=True)
class OperationResponse:
    """Base interface for operation responses.

    Attributes
    ----------
    timestamp : datetime
        When the response was created
    success : bool
        Whether the operation succeeded
    message : Optional[str]
        Human-readable message (error or status)
    error_code : Optional[str]
        Machine-readable error code for failures
    error_details : Optional[Dict[str, Any]]
        Additional error context and debugging information
    """

    timestamp: datetime = field(default_factory=datetime.now)

    success: bool = False
    message: str | None = None
    error_code: str | None = None
    error_details: dict[str, Any] | None = None

    @classmethod
    def from_error(cls, error: "AidbError", **kwargs):
        """Create a response from an AidbError exception.

        Parameters
        ----------
        error : AidbError
            The exception to convert
        **kwargs
            Additional fields for the response

        Returns
        -------
        OperationResponse
            Response with error information
        """
        return cls(
            success=False,
            message=str(error),
            error_code=error.error_code,
            error_details=error.details,
            **kwargs,
        )

    @staticmethod
    def extract_response_fields(
        dap_response,
    ) -> tuple[bool, str | None, str | None]:
        """Extract common response fields from DAP response.

        Parameters
        ----------
        dap_response
            The DAP response to extract from

        Returns
        -------
        tuple[bool, Optional[str], Optional[str]]
            success, message, error_code
        """
        success = getattr(dap_response, "success", True)
        message = getattr(dap_response, "message", None) if not success else None
        error_code = None

        if not success and hasattr(dap_response, "body") and dap_response.body:
            body = dap_response.body
            if hasattr(body, "error") and isinstance(body.error, dict):
                error_code = body.error.get("id")

        return success, message, error_code


T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


@dataclass(frozen=True)
class TimestampMixin:
    """Mixin providing timestamp functionality."""

    timestamp: datetime = field(default_factory=datetime.now)


class SamplingMixin:
    """Mixin providing statistical and sampling methods for collections.

    This mixin provides common methods for working with collections of items,
    particularly for sampling and statistical operations useful for AI applications
    dealing with large debug datasets.
    """

    def _get_count(self, collection: list[T] | dict[K, V]) -> int:
        """Get the count of items in a collection.

        Parameters
        ----------
        collection : Union[List[T], Dict[K, V]]
            The collection to count

        Returns
        -------
        int
            Number of items in the collection
        """
        return len(collection)

    def _calculate_reserved_spots(
        self,
        items: list[T],
        include_first: bool,
        include_last: bool,
    ) -> int:
        """Calculate number of reserved spots for first/last items.

        Parameters
        ----------
        items : List[T]
            List to sample from
        include_first : bool
            Whether to include the first item
        include_last : bool
            Whether to include the last item

        Returns
        -------
        int
            Number of reserved spots
        """
        reserved = 0
        if include_first and items:
            reserved += 1
        if include_last and len(items) > 1 and (not include_first or len(items) > 1):
            reserved += 1
        return reserved

    def _sample_middle_items(
        self,
        items: list[T],
        middle_count: int,
        include_first: bool,
        include_last: bool,
    ) -> list[T]:
        """Sample middle items evenly from a list.

        Parameters
        ----------
        items : List[T]
            List to sample from
        middle_count : int
            Number of middle items to sample
        include_first : bool
            Whether first item is included
        include_last : bool
            Whether last item is included

        Returns
        -------
        List[T]
            Sampled middle items
        """
        if middle_count <= 0:
            return []

        start_idx = 1 if include_first else 0
        end_idx = len(items) - (1 if include_last else 0)

        if end_idx <= start_idx:
            return []

        # Calculate step size for even distribution
        step = (end_idx - start_idx) / (middle_count + 1)

        # Generate indices for middle items
        result = []
        for i in range(1, middle_count + 1):
            idx = start_idx + int(i * step)
            if start_idx <= idx < end_idx:
                result.append(items[idx])

        return result

    def _sample_list(
        self,
        items: list[T],
        n: int,
        include_first: bool = True,
        include_last: bool = True,
    ) -> list[T]:
        """Sample n items from a list, optionally including first and last.

        Parameters
        ----------
        items : List[T]
            List to sample from
        n : int
            Number of items to sample
        include_first : bool, optional
            Whether to include the first item, by default True
        include_last : bool, optional
            Whether to include the last item, by default True

        Returns
        -------
        List[T]
            Sampled items
        """
        if n >= len(items):
            return list(items)

        if n <= 0:
            return []

        result = []

        # Calculate reserved spots and middle count
        reserved = self._calculate_reserved_spots(items, include_first, include_last)
        middle_count = min(n - reserved, len(items) - reserved)

        # Add first item if requested
        if include_first and items:
            result.append(items[0])

        # Sample middle items evenly
        result.extend(
            self._sample_middle_items(items, middle_count, include_first, include_last),
        )

        # Add last item if requested
        if include_last and len(items) > 0:
            result.append(items[-1])

        return result

    def _sample_dict(
        self,
        items: dict[K, V],
        n: int,
        priority_key: K | None = None,
    ) -> dict[K, V]:
        """Sample n items from a dict, optionally prioritizing a specific key.

        Parameters
        ----------
        items : Dict[K, V]
            Dictionary to sample from
        n : int
            Number of items to sample
        priority_key : Optional[K], optional
            Key to prioritize in sampling, by default None

        Returns
        -------
        Dict[K, V]
            Sampled items
        """
        if n >= len(items):
            return dict(items)

        if n <= 0:
            return {}

        result = {}

        # Add priority item if it exists
        if priority_key is not None and priority_key in items:
            result[priority_key] = items[priority_key]
            n -= 1

        # Sample remaining items evenly
        remaining_keys = [k for k in items if k != priority_key]
        if n > 0 and remaining_keys:
            step = len(remaining_keys) / n
            indices = [int(i * step) for i in range(n)]
            for i in indices:
                if i < len(remaining_keys):
                    key = remaining_keys[i]
                    result[key] = items[key]

        return result

    def _filter_dict(
        self,
        items: dict[K, V],
        predicate: Callable[[V], bool],
    ) -> dict[K, V]:
        """Filter a dictionary by a predicate function.

        Parameters
        ----------
        items : Dict[K, V]
            Dictionary to filter
        predicate : Callable[[V], bool]
            Function that returns True for items to include

        Returns
        -------
        Dict[K, V]
            Filtered dictionary
        """
        return {k: v for k, v in items.items() if predicate(v)}

    def _get_subset(self, items: list[T], n: int, start_idx: int = 0) -> list[T]:
        """Get a subset of n items from a list starting at start_idx.

        Parameters
        ----------
        items : List[T]
            List to get subset from
        n : int
            Number of items to get
        start_idx : int, optional
            Starting index, by default 0

        Returns
        -------
        List[T]
            Subset of items
        """
        if n <= 0:
            return []

        end_idx = min(start_idx + n, len(items))
        return items[start_idx:end_idx]
