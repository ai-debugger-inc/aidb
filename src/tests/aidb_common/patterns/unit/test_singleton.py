"""Tests for Singleton pattern implementation."""

import gc
import threading
import weakref
from typing import Any
from unittest.mock import Mock

import pytest

from aidb_common.patterns.singleton import Singleton


class TestSingleton(Singleton["TestSingleton"]):
    """Test singleton class."""

    _initialized: bool

    def __init__(self, value: int = 0, **kwargs: Any) -> None:
        """Initialize test singleton."""
        if not self._initialized:
            self.value = value
            self._initialized = True


class AnotherSingleton(Singleton["AnotherSingleton"]):
    """Another test singleton class."""

    _initialized: bool

    def __init__(self) -> None:
        """Initialize another singleton."""
        if not self._initialized:
            self.name = "another"
            self._initialized = True


class TestSingletonBasicBehavior:
    """Test basic singleton behavior."""

    def test_singleton_returns_same_instance(self) -> None:
        """Test that multiple calls return the same instance."""
        instance1 = TestSingleton()
        instance2 = TestSingleton()

        assert instance1 is instance2

    def test_singleton_with_init_args(self) -> None:
        """Test singleton initialization with arguments."""
        instance1 = TestSingleton(value=42)
        assert instance1.value == 42

        instance2 = TestSingleton(value=100)
        assert instance2.value == 42
        assert instance2 is instance1

    def test_different_singleton_classes_independent(self) -> None:
        """Test that different singleton classes are independent."""
        test_instance = TestSingleton(value=10)
        another_instance = AnotherSingleton()

        assert test_instance is not another_instance
        assert hasattr(test_instance, "value")
        assert hasattr(another_instance, "name")

    def test_singleton_persists_state(self) -> None:
        """Test that singleton state persists across calls."""
        instance1 = TestSingleton(value=42)
        instance1.value = 100

        instance2 = TestSingleton()
        assert instance2.value == 100


class TestSingletonReset:
    """Test singleton reset functionality."""

    def test_reset_clears_instance(self) -> None:
        """Test that reset() clears the singleton instance."""
        instance1 = TestSingleton(value=42)
        assert instance1.value == 42

        TestSingleton.reset()

        instance2 = TestSingleton(value=100)
        assert instance2.value == 100
        assert instance2 is not instance1

    def test_reset_only_affects_specific_class(self) -> None:
        """Test that reset only affects the specific singleton class."""
        test_instance = TestSingleton(value=10)
        another_instance = AnotherSingleton()

        TestSingleton.reset()

        new_test_instance = TestSingleton(value=20)
        same_another_instance = AnotherSingleton()

        assert new_test_instance is not test_instance
        assert same_another_instance is another_instance

    def test_reset_on_uninitialized_singleton(self) -> None:
        """Test that reset on uninitialized singleton doesn't raise error."""
        TestSingleton.reset()


class TestSingletonStubParameter:
    """Test singleton stub parameter for testing."""

    def test_stub_returns_new_instance(self) -> None:
        """Test that stub=True returns a new instance."""
        instance1 = TestSingleton(value=42)
        stub_instance = TestSingleton(stub=True, value=100)

        assert stub_instance is not instance1
        assert stub_instance.value == 100
        assert instance1.value == 42

    def test_stub_does_not_replace_singleton(self) -> None:
        """Test that stub instances don't replace the singleton."""
        instance1 = TestSingleton(value=42)
        stub_instance = TestSingleton(stub=True, value=100)
        instance2 = TestSingleton()

        assert instance2 is instance1
        assert stub_instance is not instance1

    def test_multiple_stubs_are_different(self) -> None:
        """Test that multiple stub instances are different."""
        stub1 = TestSingleton(stub=True, value=1)
        stub2 = TestSingleton(stub=True, value=2)

        assert stub1 is not stub2
        assert stub1.value == 1
        assert stub2.value == 2


class TestSingletonThreadSafety:
    """Test singleton thread safety."""

    def test_concurrent_access_returns_same_instance(self) -> None:
        """Test that concurrent access returns the same instance."""
        instances = []
        barrier = threading.Barrier(10)

        def create_instance() -> None:
            barrier.wait()
            instance = TestSingleton(value=42)
            instances.append(instance)

        threads = [threading.Thread(target=create_instance) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(instances) == 10
        assert all(instance is instances[0] for instance in instances)

    def test_concurrent_reset_and_access(self) -> None:
        """Test concurrent reset and access operations."""
        results: dict[str, list[Any]] = {"created": [], "errors": []}
        barrier = threading.Barrier(5)

        def access_and_reset(i: int) -> None:
            try:
                barrier.wait()
                if i % 2 == 0:
                    TestSingleton.reset()
                instance = TestSingleton(value=i)
                results["created"].append(instance)
            except Exception as e:
                results["errors"].append(e)

        threads = [
            threading.Thread(target=access_and_reset, args=(i,)) for i in range(5)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        assert len(results["errors"]) == 0
        assert len(results["created"]) == 5


class TestSingletonWeakReference:
    """Test singleton WeakKeyDictionary behavior."""

    def test_singleton_uses_weak_references(self) -> None:
        """Test that singleton uses weak references for class keys."""
        from aidb_common.patterns.singleton import Singleton

        assert isinstance(Singleton._instances, weakref.WeakKeyDictionary)

    def test_weak_reference_allows_garbage_collection(self) -> None:
        """Test that weak references allow class garbage collection."""

        class TemporarySingleton(Singleton["TemporarySingleton"]):
            """Temporary singleton for GC test."""

        instance = TemporarySingleton()
        assert TemporarySingleton in Singleton._instances

        del TemporarySingleton
        del instance
        gc.collect()


class TestSingletonTypeValidation:
    """Test singleton type validation."""

    def test_mock_instance_raises_type_error(self) -> None:
        """Test that using a mock as singleton raises TypeError."""

        class MockableSingleton(Singleton["MockableSingleton"]):
            """Singleton that will have mock injected."""

        mock_instance = Mock(spec=MockableSingleton)
        MockableSingleton._instances[MockableSingleton] = mock_instance

        with pytest.raises(TypeError, match="must be a real instance"):
            _ = MockableSingleton()

    def test_none_instance_raises_type_error(self) -> None:
        """Test that None instance raises TypeError."""

        class NullableSingleton(Singleton["NullableSingleton"]):
            """Singleton that will have None injected."""

        NullableSingleton._instances[NullableSingleton] = None  # type: ignore[assignment]

        with pytest.raises(TypeError, match="must be a real instance"):
            _ = NullableSingleton()


class TestSingletonEdgeCases:
    """Test singleton edge cases."""

    def test_singleton_with_no_init(self) -> None:
        """Test singleton class with no __init__ method."""

        class NoInitSingleton(Singleton["NoInitSingleton"]):
            """Singleton without __init__."""

        instance1 = NoInitSingleton()
        instance2 = NoInitSingleton()

        assert instance1 is instance2

    def test_singleton_with_complex_inheritance(self) -> None:
        """Test singleton with multiple inheritance levels."""

        class BaseSingleton(Singleton["BaseSingleton"]):
            """Base singleton."""

            _initialized: bool

            def __init__(self) -> None:
                """Initialize base."""
                if not self._initialized:
                    self.base_value = "base"
                    self._initialized = True

        class DerivedSingleton(BaseSingleton):
            """Derived singleton."""

            def __init__(self) -> None:
                """Initialize derived."""
                super().__init__()
                if not hasattr(self, "derived_value"):
                    self.derived_value = "derived"

        instance1 = DerivedSingleton()
        instance2 = DerivedSingleton()

        assert instance1 is instance2
        assert instance1.base_value == "base"
        assert instance1.derived_value == "derived"

    def test_singleton_initialization_flag(self) -> None:
        """Test that _initialized flag works correctly."""

        class FlagSingleton(Singleton["FlagSingleton"]):
            """Singleton that tracks initialization."""

            _initialized: bool

            def __init__(self) -> None:
                """Initialize with counter."""
                if not self._initialized:
                    self.init_count = 1
                    self._initialized = True
                else:
                    self.init_count += 1

        instance1 = FlagSingleton()
        assert instance1.init_count == 1

        instance2 = FlagSingleton()
        assert instance2.init_count == 2
        assert instance2 is instance1
