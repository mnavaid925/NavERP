"""HRM 3.23 Learning Management (LMS) — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403


# ------------------------------------------------------------ Gamification leaderboard (3.23, computed)
# Point thresholds -> level tier (a computed feature, no stored table). Lowest-first; the level is the
# highest threshold the learner's total points meet.
_LMS_LEVEL_THRESHOLDS = [(0, "Bronze"), (150, "Silver"), (400, "Gold"), (800, "Platinum")]


def _lms_level_for_points(points):
    level = _LMS_LEVEL_THRESHOLDS[0][1]
    for threshold, name in _LMS_LEVEL_THRESHOLDS:
        if points >= threshold:
            level = name
    return level
