"""Exception-related response models."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..base import OperationResponse
from ..entities.exception import ExceptionInfo
from ..entities.stack import AidbStackFrame, SourceLocation

if TYPE_CHECKING:
    from aidb.dap.protocol.responses import ExceptionInfoResponse


@dataclass(frozen=True)
class AidbExceptionResponse(OperationResponse):
    """Response containing exception information."""

    exception: ExceptionInfo | None = None
    thread_id: int = 0

    @classmethod
    def from_dap(cls, dap_response: "ExceptionInfoResponse") -> "AidbExceptionResponse":
        """Create AidbExceptionResponse from DAP ExceptionInfoResponse.

        This consolidates the mapper logic directly into the model.

        Parameters
        ----------
        dap_response : ExceptionInfoResponse
            The DAP exception info response to convert

        Returns
        -------
        AidbExceptionResponse
            The converted exception response
        """
        # Extract exception info
        exception_info = None
        if dap_response.body:
            body = dap_response.body

            # Extract message
            message = "Unknown exception"
            if hasattr(body, "description") and body.description:
                message = body.description
            elif hasattr(body, "details") and body.details:
                if isinstance(body.details, dict) and "message" in body.details:
                    message = body.details["message"]
                elif isinstance(body.details, str):
                    message = body.details

            # Parse stack frames if available
            stack_frames = []
            if hasattr(body, "details") and body.details:
                details = body.details
                if hasattr(details, "stackTrace") and details.stackTrace:
                    stack_frames = cls._parse_text_stack_trace(details.stackTrace)

            exception_info = ExceptionInfo(
                type_name=body.exceptionId or "Unknown",
                message=message,
                description=body.description,
                stack_frames=stack_frames,
            )
        else:
            exception_info = ExceptionInfo(
                type_name="Unknown",
                message="No exception information available",
            )

        # Extract base fields
        success = dap_response.success
        message = (
            (dap_response.message or "") if hasattr(dap_response, "message") else ""
        )
        error_code = None
        if not success and hasattr(dap_response, "body") and dap_response.body:
            body = dap_response.body
            if hasattr(body, "error"):
                error_code = (
                    body.error.get("id") if isinstance(body.error, dict) else None
                )

        return cls(
            exception=exception_info,
            success=success,
            message=message,
            error_code=error_code,
        )

    @staticmethod
    def _parse_text_stack_trace(stack_trace: str) -> list[AidbStackFrame]:
        """Parse a text stack trace into structured stack frames.

        This is a best-effort parser that handles common stack trace formats.
        Different languages have different formats, so this may need
        language-specific handling in the future.

        Parameters
        ----------
        stack_trace : str
            Text representation of the stack trace

        Returns
        -------
        List[AidbStackFrame]
            List of parsed stack frames
        """
        frames: list[AidbStackFrame] = []

        if not stack_trace:
            return frames

        # Split into lines
        lines = stack_trace.strip().split("\n")

        # Simple heuristic parser - this would need to be enhanced
        # for different language formats
        frame_id = 0
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Try to extract file path and line number
            # Common patterns:
            # Python: File "path/to/file.py", line 123, in function_name
            # Java: at com.example.Class.method(File.java:123)
            # JavaScript: at functionName (file:///path/to/file.js:123:45)

            # For now, create a simple frame with the line as the name
            # A real implementation would parse based on language
            frame = AidbStackFrame(
                id=frame_id,
                name=line[:100] if len(line) > 100 else line,  # Truncate long lines
                source=SourceLocation(path="<unknown>", line=0),
                module="<unknown>",
            )
            frames.append(frame)
            frame_id += 1

        return frames
