"""Docker profile resolution for test orchestration.

This module determines the appropriate Docker Compose profile based on test suite
and target paths. Profile is automatically inferred - no manual override needed.
"""

from aidb_cli.core.constants import DockerProfiles
from aidb_common.constants import Language
from aidb_logging import get_cli_logger

logger = get_cli_logger(__name__)


class TestProfileResolver:
    """Resolves Docker Compose profiles for test execution.

    Uses a clear priority system to determine the most appropriate profile:
    1. Language detection from target path
    2. Suite name mapping
    3. Default to base profile
    """

    @staticmethod
    def determine_profile(
        suite: str | None,
        target: list[str] | None,
    ) -> str:
        """Determine the appropriate Docker profile.

        Priority order (highest to lowest):
        1. Language detection from target path (frameworks/python/ → python)
        2. Suite mapping (mcp → mcp, core → core, etc.)
        3. Default to base profile (minimal profile)

        Parameters
        ----------
        suite : str | None
            Test suite name
        target : list[str] | None
            Specific test target paths (uses first target for profile detection)

        Returns
        -------
        str
            Docker compose profile to use
        """
        logger.debug(
            "Determining Docker profile: suite='%s', target='%s'",
            suite,
            target,
        )

        # Priority 1: Detect language from target path
        # Use first target for profile detection
        if target:
            first_target = target[0]
            # Check each supported language
            for lang in Language:
                lang_path = f"frameworks/{lang.value}"
                if f"/{lang_path}/" in first_target or lang_path in first_target:
                    logger.debug(
                        "Detected %s tests from target path",
                        lang.value.capitalize(),
                    )
                    return lang.value
            # If frameworks/ without specific language, use frameworks profile
            if "/frameworks/" in first_target or "frameworks" in first_target:
                logger.debug("Detected multi-language framework tests")
                return "frameworks"

        # Priority 2: Use suite name as profile
        # Convention: suite names match profile names, with special cases
        if suite:
            # Special cases that should use base profile
            if suite in DockerProfiles.BASE_PROFILE_SUITES:
                logger.debug("Suite '%s' maps to base profile (special case)", suite)
                return DockerProfiles.BASE

            # Known profiles use their own name
            if suite in DockerProfiles.ALL_PROFILES:
                logger.debug("Using suite '%s' as profile name (known profile)", suite)
                return suite

            # Unknown suites default to base for safety
            logger.debug(
                "Unknown suite '%s', defaulting to base profile",
                suite,
            )
            return DockerProfiles.BASE

        # Priority 3: Default to minimal base profile
        logger.debug("No suite/profile specified, defaulting to base profile")
        return DockerProfiles.BASE
