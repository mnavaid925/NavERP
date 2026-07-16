"""HRM 3.6 Candidate Management — HEX_COLOR_VALIDATORs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# Hex-color validator for tag badges (no shared core validator exists yet).
HEX_COLOR_VALIDATOR = RegexValidator(r"^#[0-9A-Fa-f]{6}$", "Enter a valid hex color, e.g. #3B82F6.")
