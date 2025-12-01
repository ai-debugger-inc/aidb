"""AidbBreakpoint converter for transforming user-friendly formats to DAP."""

from typing import TYPE_CHECKING, Optional

from aidb.common.errors import AidbError
from aidb.models import AidbBreakpoint, BreakpointState
from aidb.models.entities.breakpoint import BreakpointSpec
from aidb.patterns import Obj

if TYPE_CHECKING:
    from aidb.interfaces.context import IContext

from .breakpoint_utils import convert_breakpoints, process_breakpoint_inputs


class BreakpointConverter(Obj):
    """Convert user-friendly breakpoint formats to DAP requests."""

    def __init__(self, ctx: Optional["IContext"] = None):
        """Initialize the BreakpointConverter.

        Parameters
        ----------
        ctx : IContext, optional
            Application context
        """
        super().__init__(ctx)

    def convert(
        self,
        breakpoints: list[BreakpointSpec] | BreakpointSpec,
        _target: str,
        language: str | None = None,
    ) -> list[AidbBreakpoint]:
        """Convert user breakpoints to AidbBreakpoint format.

        Parameters
        ----------
        breakpoints : Union[List[BreakpointSpec], BreakpointSpec]
            Breakpoint specifications conforming to BreakpointSpec schema
        target : str
            Default target file for breakpoints (unused, file comes from spec)
        language : str, optional
            Language for adapter-specific validation

        Returns
        -------
        List[AidbBreakpoint]
            List of AidbBreakpoint instances ready for use

        Raises
        ------
        AidbError
            If conversion fails
        """
        if not breakpoints:
            self.ctx.debug("BreakpointConverter.convert: No breakpoints provided")
            return []

        self.ctx.debug(
            f"BreakpointConverter.convert: Processing "
            f"{len(breakpoints) if isinstance(breakpoints, list) else 1} "
            f"breakpoint(s) for language={language}",
        )

        try:
            # Get adapter class if language specified
            adapter_class = None
            if language:
                try:
                    from aidb.session.adapter_registry import AdapterRegistry

                    registry = AdapterRegistry(self.ctx)
                    adapter_class = registry.get_adapter_class(language)
                    self.ctx.debug(
                        f"BreakpointConverter: Got adapter class for {language}",
                    )
                except Exception as e:
                    msg = f"Failed to get adapter class for language '{language}': {e}"
                    self.ctx.debug(msg)

            # Process and convert breakpoints
            processed = process_breakpoint_inputs(breakpoints)
            self.ctx.debug(
                f"BreakpointConverter: Processed {len(processed)} breakpoint input(s)",
            )
            dap_requests = convert_breakpoints(processed, adapter=adapter_class)
            self.ctx.debug(
                f"BreakpointConverter: Created {len(dap_requests)} DAP request(s)",
            )

            # Convert SetBreakpointsRequest objects to AidbBreakpoint objects

            aidb_breakpoints = []

            for request in dap_requests:
                if request.arguments and request.arguments.source:
                    source_path = request.arguments.source.path
                    if source_path and request.arguments.breakpoints:
                        for i, bp in enumerate(request.arguments.breakpoints):
                            aidb_bp = AidbBreakpoint(
                                id=i,  # Will be updated when actually set
                                source_path=source_path,
                                line=bp.line,
                                verified=False,  # Not verified until set
                                state=BreakpointState.PENDING,
                                condition=bp.condition or "",
                                hit_condition=bp.hitCondition or "",
                                log_message=bp.logMessage or "",
                                column=bp.column or 0,
                            )
                            aidb_breakpoints.append(aidb_bp)

            self.ctx.debug(
                f"Converted {len(processed)} user breakpoints "
                f"to {len(aidb_breakpoints)} AidbBreakpoint objects",
            )

            return aidb_breakpoints

        except ValueError as e:
            self.ctx.error(f"Breakpoint conversion failed: {e}")
            msg = f"Invalid breakpoint format: {e}"
            raise AidbError(msg) from e

    def validate(
        self,
        breakpoints: list[BreakpointSpec] | BreakpointSpec,
        target: str,
        language: str | None = None,
    ) -> list[str]:
        """Validate breakpoints without converting.

        Parameters
        ----------
        breakpoints : Union[List[BreakpointSpec], BreakpointSpec]
            Breakpoint specifications to validate
        target : str
            Default target file (unused, file comes from spec)
        language : str, optional
            Language for adapter-specific validation

        Returns
        -------
        List[str]
            List of validation errors (empty if all valid)
        """
        errors = []

        try:
            self.convert(breakpoints, target, language)
        except AidbError as e:
            errors.append(str(e))
        except Exception as e:
            self.ctx.error(f"Unexpected breakpoint validation error: {e}")
            errors.append(f"Unexpected error: {e}")

        return errors
