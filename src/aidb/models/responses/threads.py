"""Thread-related response models."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..base import OperationResponse, SamplingMixin
from ..entities.thread import AidbThread, ThreadState

if TYPE_CHECKING:
    from aidb.dap.protocol.responses import ThreadsResponse


@dataclass(frozen=True)
class AidbThreadsResponse(OperationResponse, SamplingMixin):
    """Response containing information about threads."""

    threads: dict[int, AidbThread] = field(default_factory=dict)
    current_thread_id: int | None = None

    @property
    def current_thread(self) -> Any | None:
        """Get the current thread."""
        if self.current_thread_id is not None:
            return self.threads.get(self.current_thread_id)
        return None

    @property
    def stopped_threads(self) -> list[Any]:
        """Get all stopped threads."""
        return [t for t in self.threads.values() if t.is_stopped]

    @property
    def count(self) -> int:
        """Get the total number of threads."""
        return self._get_count(self.threads)

    @property
    def running_count(self) -> int:
        """Get the number of running threads."""
        return len([t for t in self.threads.values() if t.is_running])

    @property
    def stopped_count(self) -> int:
        """Get the number of stopped threads."""
        return len(self.stopped_threads)

    def sample(self, n: int = 10) -> dict[int, Any]:
        """Sample n threads from the collection.

        Parameters
        ----------
        n : int, optional
            Number of threads to sample, by default 10

        Returns
        -------
        Dict[int, Thread]
            Sampled threads
        """
        return self._sample_dict(self.threads, n, priority_key=self.current_thread_id)

    def by_state(self, state: Any) -> dict[int, Any]:
        """Get threads in a specific state.

        Parameters
        ----------
        state : ThreadState
            State of threads to get

        Returns
        -------
        Dict[int, Thread]
            Threads in the specified state
        """
        return self._filter_dict(self.threads, lambda t: t.state == state)

    def running_threads(self) -> dict[int, Any]:
        """Get all running threads.

        Returns
        -------
        Dict[int, Thread]
            Running threads
        """
        return self.by_state(ThreadState.RUNNING)

    @classmethod
    def from_dap(
        cls,
        dap_response: "ThreadsResponse",
        thread_states: dict[int, ThreadState] | None = None,
    ) -> "AidbThreadsResponse":
        """Create AidbThreadsResponse from DAP ThreadsResponse.

        This consolidates the mapper logic directly into the model.

        Parameters
        ----------
        dap_response : ThreadsResponse
            The DAP threads response to convert
        thread_states : Optional[Dict[int, ThreadState]]
            Optional dictionary of thread states tracked via events.
            Maps thread ID to current ThreadState.

        Returns
        -------
        AidbThreadsResponse
            The converted threads response
        """
        threads: dict[int, AidbThread] = {}
        thread_states = thread_states or {}

        # Extract threads from DAP response
        if dap_response.body and dap_response.body.threads:
            for dap_thread in dap_response.body.threads:
                # Determine thread state
                state = thread_states.get(dap_thread.id, ThreadState.RUNNING)

                thread = AidbThread(
                    id=dap_thread.id,
                    name=dap_thread.name,
                    state=state,
                )
                threads[thread.id] = thread

        # Determine active thread
        current_thread_id = 0
        if threads:
            # Look for a stopped thread (likely hit a breakpoint)
            for thread_id, thread in threads.items():
                if thread.state == ThreadState.STOPPED:
                    current_thread_id = thread_id
                    break
            else:
                # Otherwise return the first thread (usually main thread)
                current_thread_id = next(iter(threads.keys()))

        # Extract base fields
        success = dap_response.success
        message = dap_response.message if hasattr(dap_response, "message") else None
        error_code = None
        if not success and hasattr(dap_response, "body"):
            body = dap_response.body
            if body and hasattr(body, "error"):
                error_code = (
                    body.error.get("id") if isinstance(body.error, dict) else None
                )

        return cls(
            threads=threads,
            current_thread_id=current_thread_id,
            success=success,
            message=message,
            error_code=error_code,
        )
