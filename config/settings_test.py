"""Test settings — isolated SQLite in-memory DB.

pytest.ini points DJANGO_SETTINGS_MODULE here so the suite never touches the shared
MySQL dev database (lesson L19): fast, deterministic, and safe to run concurrently.

**Why `NAVERP_TEST_DB` exists.** `pytest.ini` has carried `addopts = --reuse-db` from the start,
but it could never do anything: for SQLite, Django IGNORES `DATABASES["default"]["NAME"]` when
building the *test* database and looks only at `DATABASES["default"]["TEST"]["NAME"]`, which was
unset — so the test database was always a shared in-memory one, discarded when the process exits.
Every run therefore re-applied all ~270 migrations. On this machine that is well over 20 minutes of
solid CPU, which is long enough that people (reasonably) start killing runs part-way — and a killed
run throws the work away and can leave a partial test database behind.

Point `NAVERP_TEST_DB` at a file and `--reuse-db` finally works: the first run pays the migration
cost, and every run after it starts in seconds.

    # fast iteration, migrations skipped (default in-memory DB)
    pytest apps/tenants/tests -q --no-migrations

    # the real thing: migrations applied, then cached
    $env:NAVERP_TEST_DB = "nav_erp_test.sqlite3"
    pytest apps/tenants/tests          # slow once
    pytest apps/tenants/tests          # seconds from then on
    Remove-Item nav_erp_test.sqlite3   # start over

Two details that are easy to get wrong, and cost time to find:

* The knob is **`TEST["NAME"]`**, not `NAME`. Setting `NAME` alone changes nothing about the test
  database on SQLite — Django's sqlite3 backend substitutes a shared in-memory URI unless
  `TEST["NAME"]` is given.
* Use a **bare filename**, not a path. Django takes the test database name from `TEST["NAME"]`
  verbatim, so `temp/x.sqlite3` becomes a literal file name in the project root rather than a file
  inside `temp/`.

The default stays in-memory, so an ordinary run is still isolated and still safe to run concurrently.
"""
import os

from .settings import *  # noqa: F401,F403

_NAVERP_TEST_DB = os.environ.get("NAVERP_TEST_DB") or None

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        **({"TEST": {"NAME": _NAVERP_TEST_DB}} if _NAVERP_TEST_DB else {}),
    }
}

# Speed: cheap hasher + in-memory email.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

DEBUG = False
STRIPE_ENABLED = False
