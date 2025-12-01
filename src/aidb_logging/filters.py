"""Custom logging filters for aidb_logging package."""

import inspect
import logging
import threading
from collections import OrderedDict
from pathlib import Path

from .context import get_request_id, get_session_id


class CallerFilter(logging.Filter):
    """Filter that adds real caller information to log records.

    This filter walks the stack to find the actual calling code, skipping logging
    framework internals to provide accurate module, function, and line number
    information.
    """

    # Default modules and functions to skip
    DEFAULT_SKIP_MODULES = {
        "logging",
        "logger",
        "filters",
        "handlers",
        "formatters",
        "context",
        "config",
        "performance",
        "aidb_logging",
    }

    DEFAULT_SKIP_FUNCTIONS = {
        "_log",
        "filter",
        "emit",
        "format",
        "handle",
        "callHandlers",
        "pytest_pyfunc_call",
    }

    def __init__(
        self,
        skip_modules: set[str] | None = None,
        skip_functions: set[str] | None = None,
        enable_cache: bool = True,
        cache_size: int = 128,
    ) -> None:
        """Initialize the CallerFilter with configurable skip patterns.

        Parameters
        ----------
        skip_modules : set[str], optional
            Additional module names/patterns to skip
        skip_functions : set[str], optional
            Additional function names to skip
        enable_cache : bool
            Enable caching for performance (default: True)
        cache_size : int
            LRU cache size (default: 128 entries)
        """
        super().__init__()
        self.skip_modules = self.DEFAULT_SKIP_MODULES.copy()
        if skip_modules:
            self.skip_modules.update(skip_modules)

        self.skip_functions = self.DEFAULT_SKIP_FUNCTIONS.copy()
        if skip_functions:
            self.skip_functions.update(skip_functions)

        # Optional small LRU cache keyed by (pathname, funcName, lineno, thread)
        self.enable_cache = enable_cache
        self._cache_size = max(1, cache_size)
        self._cache: OrderedDict[tuple[str, str, int, int], tuple[str, int, str]] | None
        self._cache = OrderedDict() if enable_cache else None

    def filter(self, record: logging.LogRecord) -> bool:
        """Add real caller information to the log record.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to enhance

        Returns
        -------
        bool
            Always returns True to pass the record through
        """
        # Use a caching key based on the apparent site and current thread
        module_name: str
        line_no: int
        func_name: str

        if self.enable_cache and self._cache is not None:
            key = (
                getattr(record, "pathname", ""),
                getattr(record, "funcName", ""),
                getattr(record, "lineno", 0),
                threading.get_ident(),
            )
            cached = self._cache.get(key)
            if cached is not None:
                # Refresh LRU position
                self._cache.move_to_end(key)
                module_name, line_no, func_name = cached
            else:
                module_name, line_no, func_name = self._find_real_caller_impl()
                self._cache[key] = (module_name, line_no, func_name)
                if len(self._cache) > self._cache_size:
                    # Evict the oldest entry
                    self._cache.popitem(last=False)
        else:
            module_name, line_no, func_name = self._find_real_caller_impl()

        record.real_module = module_name
        record.real_lineno = line_no
        record.real_funcName = func_name

        return True

    def _find_real_caller_impl(self) -> tuple[str, int, str]:
        """Find the real caller by walking the stack.

        Returns
        -------
        tuple[str, int, str]
            Module name, line number, and function name
        """
        frames = inspect.stack()

        # Walk the stack to find the real caller
        for frame_info in frames:
            module_path = frame_info.filename

            # Skip logging infrastructure frames
            if self._should_skip_frame(module_path, frame_info.function, frame_info):
                continue

            # Found the real caller
            filename = Path(frame_info.filename).name
            module_name = Path(filename).stem
            return module_name, frame_info.lineno, frame_info.function

        # Fallback if no suitable frame found
        return "unknown", 0, "unknown"

    def _should_skip_frame(
        self,
        module_path: str,
        function_name: str,
        frame_info: inspect.FrameInfo,  # noqa: ARG002
    ) -> bool:
        """Check if a stack frame should be skipped.

        Parameters
        ----------
        module_path : str
            Path to the module file
        function_name : str
            Name of the function
        frame_info : inspect.FrameInfo
            Complete frame information for advanced checks

        Returns
        -------
        bool
            True if the frame should be skipped
        """
        module_path_lower = module_path.lower()
        for skip_module in self.skip_modules:
            # Support both substring matching and path component matching
            if skip_module in module_path_lower:
                return True
            # Check if it's a path component (more precise)
            path_parts = Path(module_path).parts
            if any(skip_module in part.lower() for part in path_parts):
                return True

        if function_name in self.skip_functions:
            return True

        # Check for frozen/compiled module paths (e.g., <frozen importlib._bootstrap>)
        if module_path.startswith("<") and module_path.endswith(">"):
            if "<frozen" not in module_path.lower():
                return False  # Don't skip user code
            # Skip frozen logging infrastructure
            return any(skip in module_path.lower() for skip in self.skip_modules)

        return False


class SessionContextFilter(logging.Filter):
    """Filter that adds session and request context to log records.

    Adds session_id and request_id from context variables to all log records for better
    debugging and tracing capabilities.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add session and request context to the record.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to enhance

        Returns
        -------
        bool
            Always returns True to pass the record through
        """
        session_id = get_session_id()
        if session_id:
            # Truncate for readability
            record.session_id = f"SID:{session_id[:8]}"
        else:
            record.session_id = "NO_SESSION"

        request_id = get_request_id()
        if request_id:
            record.request_id = request_id
        else:
            record.request_id = "NO_REQUEST"

        return True


class LevelFilter(logging.Filter):
    """Filter that only allows specific log levels through.

    Useful for routing different levels to different handlers.
    """

    def __init__(
        self,
        min_level: int | None = None,
        max_level: int | None = None,
    ) -> None:
        """Initialize the level filter.

        Parameters
        ----------
        min_level : int, optional
            Minimum log level to allow (inclusive)
        max_level : int, optional
            Maximum log level to allow (inclusive)
        """
        super().__init__()
        self.min_level = min_level or logging.DEBUG
        self.max_level = max_level or logging.CRITICAL

    def filter(self, record: logging.LogRecord) -> bool:
        """Check if record's level is within allowed range.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to check

        Returns
        -------
        bool
            True if the record's level is within range
        """
        return self.min_level <= record.levelno <= self.max_level


class ModuleFilter(logging.Filter):
    """Filter that includes or excludes specific modules.

    Useful for filtering logs from specific packages or modules.
    """

    def __init__(
        self,
        include_modules: list[str] | None = None,
        exclude_modules: list[str] | None = None,
    ) -> None:
        """Initialize the module filter.

        Parameters
        ----------
        include_modules : list[str], optional
            Only include logs from these modules
        exclude_modules : list[str], optional
            Exclude logs from these modules
        """
        super().__init__()
        self.include_modules = include_modules or []
        self.exclude_modules = exclude_modules or []

    def filter(self, record: logging.LogRecord) -> bool:
        """Check if record's module should be included.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to check

        Returns
        -------
        bool
            True if the record should be included
        """
        module_name = record.name

        # If include list is specified, module must be in it
        if self.include_modules and not any(
            module_name.startswith(inc) for inc in self.include_modules
        ):
            return False

        return not (
            self.exclude_modules
            and any(module_name.startswith(exc) for exc in self.exclude_modules)
        )
