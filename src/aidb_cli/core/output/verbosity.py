"""Verbosity level enum for CLI output."""

from enum import IntEnum


class Verbosity(IntEnum):
    """Verbosity levels for CLI output.

    Levels are ordered from least to most verbose:
    - NORMAL: Default output (progress, results, errors, warnings)
    - VERBOSE: -v flag (+ operation details, step-by-step info)
    - DEBUG: -vvv flag (+ full streaming, protocol traces)
    """

    NORMAL = 0
    VERBOSE = 1
    DEBUG = 2

    @classmethod
    def from_flags(
        cls,
        verbose: bool = False,
        verbose_debug: bool = False,
    ) -> "Verbosity":
        """Create Verbosity from CLI flags.

        Parameters
        ----------
        verbose : bool
            Whether -v flag is set
        verbose_debug : bool
            Whether -vvv flag is set

        Returns
        -------
        Verbosity
            Corresponding verbosity level
        """
        if verbose_debug:
            return cls.DEBUG
        if verbose:
            return cls.VERBOSE
        return cls.NORMAL
