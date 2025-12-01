"""Django settings for test_project.

This is a minimal Django configuration for testing debugging capabilities.
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "django-insecure-test-key-not-for-production"

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "test_project.urls"

TEMPLATES = []

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    },
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
