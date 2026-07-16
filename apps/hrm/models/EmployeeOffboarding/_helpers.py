"""HRM 3.4 Employee Offboarding — _helpers models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# 1–5 Likert bound, reused across the exit-interview rating fields. A tuple so an accidental
# append in a test/migration can't leak an extra validator onto all eight fields.
_RATING_VALIDATORS = (MinValueValidator(1), MaxValueValidator(5))
