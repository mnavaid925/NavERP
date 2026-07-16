"""HRM 3.32 Analytics Dashboard — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403


def _can_share_hrdash(user):
    # Publishing (is_shared) / defaulting (is_default) a dashboard is a tenant-wide setting.
    return bool(user.is_superuser or getattr(user, "is_tenant_admin", False))


def _can_manage_hrdash(user, dashboard):
    # The owner, a tenant admin, or a superuser may edit/delete a dashboard + its widgets.
    return bool(dashboard.owner_id == user.pk or user.is_superuser
                or getattr(user, "is_tenant_admin", False))


def _bench_target(request, key):
    """Parse an optional ?target_* float, never trusting raw GET into a bare float(). Rejects
    non-finite values (nan/inf slip past float() and would drive a nonsensical RAG comparison)."""
    try:
        raw = request.GET.get(key)
        if raw in (None, ""):
            return None
        v = float(raw)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None
