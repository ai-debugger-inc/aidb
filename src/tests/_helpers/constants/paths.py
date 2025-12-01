"""Path configuration for AIDB test suite."""

from pathlib import Path

TESTS_ROOT = Path(__file__).parent.parent.parent
FRAMEWORK_APPS_ROOT = TESTS_ROOT / "_assets" / "framework_apps"


def get_framework_app_path(language: str, framework: str) -> Path:
    """Get the path to a framework test application.

    Framework applications are organized by language in the test assets directory:
    tests/_assets/framework_apps/{language}/{framework}_app/

    Parameters
    ----------
    language : str
        Programming language (e.g., 'javascript', 'python', 'java')
    framework : str
        Framework name (e.g., 'express', 'django', 'flask')

    Returns
    -------
    Path
        Absolute path to the framework application directory

    Examples
    --------
    >>> get_framework_app_path("javascript", "express")
    Path('.../tests/_assets/framework_apps/javascript/express_app')

    >>> get_framework_app_path("python", "django")
    Path('.../tests/_assets/framework_apps/python/django_app')

    >>> get_framework_app_path("java", "spring")
    Path('.../tests/_assets/framework_apps/java/spring_app')
    """
    return FRAMEWORK_APPS_ROOT / language / f"{framework}_app"


__all__ = [
    "FRAMEWORK_APPS_ROOT",
    "TESTS_ROOT",
    "get_framework_app_path",
]
