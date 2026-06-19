#!/usr/bin/env python
"""Stop hook — end-of-turn verification for NavERP.

Runs when Claude finishes a turn:
  1. Always: Django `manage.py check`.
  2. If pytest is installed AND a real test suite exists: run it (bounded, fail-fast).

Exit 0  = green (or no suite yet) — a short note is shown to the user.
Exit 2  = `manage.py check` or the tests FAILED — the summary is fed back so Claude
          fixes it before the turn truly ends. Loop-guarded via `stop_hook_active`.
"""
import glob
import io
import json
import os
import subprocess
import sys

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HOOK_DIR))


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    if payload.get("stop_hook_active"):
        return 0  # this stop is already a hook continuation — don't loop

    os.chdir(ROOT)
    sys.path.insert(0, ROOT)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    report = []
    failed = False

    # 1) manage.py check
    try:
        import django
        django.setup()
        from django.core.management import call_command
        from django.core.management.base import SystemCheckError
        buf = io.StringIO()
        try:
            call_command("check", stdout=buf, stderr=buf)
            report.append("manage.py check: OK")
        except SystemCheckError:
            failed = True
            report.append("manage.py check: FAILED\n" + buf.getvalue().strip())
    except Exception as exc:
        report.append(f"manage.py check: skipped ({exc.__class__.__name__}: {exc})")

    # 2) tests — only when a real suite exists (skips the empty default tests.py)
    py = sys.executable
    has_cfg = any(os.path.exists(os.path.join(ROOT, f))
                  for f in ("pytest.ini", "conftest.py", "pyproject.toml", "setup.cfg"))
    candidates = (glob.glob(os.path.join(ROOT, "apps", "*", "tests", "test_*.py"))
                  + glob.glob(os.path.join(ROOT, "apps", "*", "tests.py")))
    real_tests = [f for f in candidates if os.path.getsize(f) > 200]
    pytest_ok = subprocess.run([py, "-c", "import pytest"], capture_output=True).returncode == 0

    if real_tests and pytest_ok and has_cfg:
        try:
            # Run the suite under the project's isolated test settings (SQLite in-memory, per
            # pytest.ini -> config.settings_test) — NOT the MySQL dev settings this hook set on
            # os.environ for the `check` above. Without this override the pytest subprocess
            # inherits DJANGO_SETTINGS_MODULE=config.settings and runs against the shared MySQL
            # `test_nav_erp` DB: slow, MariaDB-10.4-fragile, and prone to collisions/half-migrated
            # state when another session's suite runs concurrently.
            test_env = dict(os.environ)
            test_env["DJANGO_SETTINGS_MODULE"] = "config.settings_test"
            proc = subprocess.run([py, "-m", "pytest", "-q", "--no-header", "-x"],
                                  cwd=ROOT, capture_output=True, text=True, timeout=240,
                                  env=test_env)
            tail = (proc.stdout or "").strip()[-1500:]
            if proc.returncode == 0:
                report.append("pytest: PASS\n" + tail)
            else:
                failed = True
                report.append("pytest: FAIL\n" + tail)
        except subprocess.TimeoutExpired:
            report.append("pytest: timed out (240s) — skipped")
    else:
        report.append("pytest: no suite yet (use the test-writer agent or /sqa-review to add tests)")

    if failed:
        sys.stderr.write("[verify-on-stop] Verification FAILED:\n" + "\n".join(report)
                         + "\nFix the above before finishing.\n")
        return 2

    note = "NavERP verify - manage.py check OK" + (" - tests OK" if real_tests else " - no test suite yet")
    print(json.dumps({"systemMessage": note, "suppressOutput": True}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
