"""HRM 3.39 Compliance & Legal — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403


# ---- HR policies (readable by all; writes admin-only) ------------------------------------------
def _annotate_policy_acks(qs):
    """Annotate the acknowledgment counts that HRPolicy's properties prefer. Without this the
    acknowledged_count / target_count / acknowledgment_rate properties each fire their own COUNT — once
    per row on the list, and up to 4 times on a single detail page."""
    return qs.annotate(
        _target_count=Count("acknowledgments", distinct=True),
        _acknowledged_count=Count("acknowledgments",
                                  filter=Q(acknowledgments__status="acknowledged"), distinct=True))
