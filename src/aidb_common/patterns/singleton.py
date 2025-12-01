"""Base singleton implementation shared across AIDB packages."""

from __future__ import annotations

import threading
import weakref
from typing import Any, ClassVar, Generic, TypeVar

T = TypeVar("T")

# Module-level lock for all singleton operations
_singleton_lock = threading.RLock()


class Singleton(Generic[T]):
    """Thread-safe singleton base class.

    Inherit from this class to make a class a singleton. Ensures only one
    instance exists per subclass and provides a reset() helper for tests.

    Keyword Args
    ------------
    stub : bool, default=False
        If True, return a new instance instead of the singleton. Primarily used
        for testing.
    """

    # Use WeakKeyDictionary to prevent memory leaks
    _instances: ClassVar[weakref.WeakKeyDictionary[Any, object]] = (
        weakref.WeakKeyDictionary()
    )
    _initialized: bool = False

    def __new__(cls, *_args: Any, **_kwargs: Any) -> Any:
        """Create or return the singleton instance.

        Returns a new instance if stub=True, otherwise returns the singleton. Enforces
        that only real instances of the class can become the singleton (not mocks or
        other types).
        """

        def _validate_instance_type(instance: Any) -> None:
            if type(instance) is not cls:
                msg = (
                    f"Singleton for {cls.__name__} must be a real instance, "
                    f"not {type(instance)}"
                )
                raise TypeError(msg)

        stub: bool = _kwargs.pop("stub", False)
        if stub:
            return super().__new__(cls)

        with _singleton_lock:
            if cls not in Singleton._instances:
                instance = super().__new__(cls)
                _validate_instance_type(instance)
                Singleton._instances[cls] = instance

            instance = Singleton._instances[cls]  # type: ignore[assignment]
            _validate_instance_type(instance)
            if instance is None:
                msg = f"Singleton instance for {cls.__name__} is None after initialization"
                raise RuntimeError(
                    msg,
                )

            return instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (primarily for tests)."""
        with _singleton_lock:
            if cls in Singleton._instances:
                del Singleton._instances[cls]
