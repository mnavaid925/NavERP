"""Test settings — isolated SQLite in-memory DB.

pytest.ini points DJANGO_SETTINGS_MODULE here so the suite never touches the shared
MySQL dev database (lesson L19): fast, deterministic, and safe to run concurrently.
"""
from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Speed: cheap hasher + in-memory email.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

DEBUG = False
STRIPE_ENABLED = False
