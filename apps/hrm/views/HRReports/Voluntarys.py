"""HRM 3.28 HR Reports — Voluntarys views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403


VOLUNTARY_SEPARATION_TYPES = {"resignation", "retirement", "contract_end"}
