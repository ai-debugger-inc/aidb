"""Output strategy module for unified CLI output with verbosity contracts.

This module provides a unified output abstraction for the CLI with explicit
verbosity contracts:

========  =========  =====================================  =========
Level     Flag       User Sees                              Streaming
========  =========  =====================================  =========
NORMAL    (default)  Progress, results, errors, warnings    No
VERBOSE   -v         + Operation details, step-by-step      TTY only
DEBUG     -vvv       + Full subprocess output, traces       TTY only
========  =========  =====================================  =========

Usage
-----
>>> from aidb_cli.core.output import OutputStrategy, Verbosity
>>>
>>> # In a command:
>>> output = ctx.obj.output
>>> output.success("Build complete")
>>> output.info("Additional details...")  # Only shown with -v
"""

from aidb_cli.core.output.protocol import OutputStrategyProtocol
from aidb_cli.core.output.strategy import OutputStrategy
from aidb_cli.core.output.verbosity import Verbosity

__all__ = [
    "OutputStrategy",
    "OutputStrategyProtocol",
    "Verbosity",
]
