"""Stack-related response models."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from aidb.common.code_context import CodeContext

from ..base import OperationResponse, SamplingMixin
from ..entities.stack import AidbStackFrame, SourceLocation

if TYPE_CHECKING:
    from aidb.dap.protocol.responses import StackTraceResponse


@dataclass(frozen=True)
class AidbCallStackResponse(OperationResponse, SamplingMixin):
    """A call stack of stack frames."""

    frames: list[AidbStackFrame] = field(default_factory=list)
    current_frame_id: int | None = None

    @property
    def current_frame(self) -> Any | None:
        """Get the current frame."""
        if self.current_frame_id is not None:
            for frame in self.frames:
                if frame.id == self.current_frame_id:
                    return frame
        return None

    @property
    def top_frame(self) -> Any | None:
        """Get the top frame."""
        if self.frames:
            return self.frames[0]
        return None

    @property
    def count(self) -> int:
        """Get the total number of frames in the stack."""
        return self._get_count(self.frames)

    def sample(self, n: int = 10) -> list[Any]:
        """Sample n frames from the stack.

        Parameters
        ----------
        n : int, optional
            Number of frames to sample, by default 10

        Returns
        -------
        List[StackFrame]
            Sampled frames
        """
        return self._sample_list(self.frames, n, include_first=True, include_last=True)

    def top(self, n: int = 5) -> list[Any]:
        """Get the top n frames from the stack.

        Parameters
        ----------
        n : int, optional
            Number of frames to get, by default 5

        Returns
        -------
        List[StackFrame]
            Top frames
        """
        return self._get_subset(self.frames, n)

    def bottom(self, n: int = 5) -> list[Any]:
        """Get the bottom n frames from the stack.

        Parameters
        ----------
        n : int, optional
            Number of frames to get, by default 5

        Returns
        -------
        List[StackFrame]
            Bottom frames
        """
        if n <= 0:
            return []

        return self.frames[-min(n, len(self.frames)) :]

    def middle(self, n: int = 5) -> list[Any]:
        """Get n frames from the middle of the stack.

        Parameters
        ----------
        n : int, optional
            Number of frames to get, by default 5

        Returns
        -------
        List[StackFrame]
            Middle frames
        """
        if n <= 0 or not self.frames:
            return []

        if n >= len(self.frames):
            return list(self.frames)

        start_idx = max(0, (len(self.frames) - n) // 2)
        return self._get_subset(self.frames, n, start_idx)

    @classmethod
    def from_dap(cls, dap_response: "StackTraceResponse") -> "AidbCallStackResponse":
        """Create AidbCallStackResponse from DAP StackTraceResponse.

        This consolidates the mapper logic directly into the model.

        Parameters
        ----------
        dap_response : StackTraceResponse
            The DAP stack trace response to convert

        Returns
        -------
        AidbCallStackResponse
            The converted call stack response
        """
        frames: list[AidbStackFrame] = []

        # Extract frames from DAP response
        if dap_response.body and dap_response.body.stackFrames:
            for dap_frame in dap_response.body.stackFrames:
                # Extract source location
                path = ""
                if hasattr(dap_frame, "source") and dap_frame.source:
                    path = (
                        dap_frame.source.path or ""
                        if hasattr(dap_frame.source, "path")
                        else ""
                    )

                source_location = SourceLocation(
                    path=path or "",
                    line=dap_frame.line,
                    column=dap_frame.column if hasattr(dap_frame, "column") else None,
                )

                # Extract code context if file path is available
                code_context = None
                if path:
                    column = dap_frame.column if hasattr(dap_frame, "column") else None
                    context_extractor = CodeContext()
                    code_context = context_extractor.extract_context(
                        path,
                        dap_frame.line,
                        column,
                    )

                # Create stack frame
                frame = AidbStackFrame(
                    id=dap_frame.id,
                    name=dap_frame.name,
                    source=source_location,
                    module=getattr(dap_frame, "moduleId", ""),
                    code_context=code_context,
                )
                frames.append(frame)

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
            frames=frames,
            current_frame_id=frames[0].id if frames else None,
            success=success,
            message=message,
            error_code=error_code,
        )

    @classmethod
    def get_frame_from_dap(
        cls,
        dap_response: "StackTraceResponse",
        frame_id: int,
    ) -> AidbStackFrame | None:
        """Extract a specific frame from DAP StackTraceResponse.

        This method provides the functionality of FrameMapper,
        extracting a single frame by ID.

        Parameters
        ----------
        dap_response : StackTraceResponse
            The DAP stack trace response
        frame_id : int
            The ID of the frame to extract

        Returns
        -------
        Optional[AidbStackFrame]
            The requested frame or None if not found
        """
        if not dap_response.body or not dap_response.body.stackFrames:
            return None

        # Find the specific frame by ID
        for dap_frame in dap_response.body.stackFrames:
            if dap_frame.id == frame_id:
                # Extract source location
                path = ""
                if hasattr(dap_frame, "source") and dap_frame.source:
                    path = (
                        dap_frame.source.path or ""
                        if hasattr(dap_frame.source, "path")
                        else ""
                    )

                source_location = SourceLocation(
                    path=path or "<unknown>",
                    line=dap_frame.line if hasattr(dap_frame, "line") else 0,
                    column=dap_frame.column if hasattr(dap_frame, "column") else 0,
                )

                # Extract code context if file path is available
                code_context = None
                if path and path != "<unknown>" and hasattr(dap_frame, "line"):
                    column = dap_frame.column if hasattr(dap_frame, "column") else None
                    context_extractor = CodeContext()
                    code_context = context_extractor.extract_context(
                        path,
                        dap_frame.line,
                        column,
                    )

                # Create and return the frame
                return AidbStackFrame(
                    id=dap_frame.id,
                    name=dap_frame.name,
                    source=source_location,
                    module=(
                        dap_frame.source.name or "<unknown>"
                        if hasattr(dap_frame, "source")
                        and dap_frame.source
                        and hasattr(dap_frame.source, "name")
                        else "<unknown>"
                    ),
                    code_context=code_context,
                )

        return None
