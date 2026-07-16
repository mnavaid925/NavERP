"""HRM 3.32 Analytics Dashboard — ANALYTICS_RANGE_CHOICESs models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.32 Analytics Dashboard — HRDashboard / HRDashboardWidget
#
# The saved custom-dashboard layer, mirroring CRM 1.6's AnalyticsDashboard/DashboardWidget: an
# HRDashboard holds HRDashboardWidget tiles computed LIVE on render (apps/hrm/analytics.py
# compute_widget) over the existing HRM data — nothing is stored. The 5 choice lists live HERE
# (next to the fields that use them) so apps/hrm/analytics.py can import them without a circular
# edge (analytics.py imports models; models.py never imports analytics.py).
# ---------------------------------------------------------------------------
ANALYTICS_RANGE_CHOICES = [
    ("last_30", "Last 30 days"),
    ("last_90", "Last 90 days"),
    ("last_180", "Last 180 days"),
    ("last_365", "Last 12 months"),
    ("ytd", "Year to date"),
    ("all", "All time"),
]
