"""HRM 3.15 Statutory Compliance — ComplianceCalendar views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    StatutoryReturn,
)


# --------------------------------------------------- Compliance calendar (cross-cutting)
@login_required
def statutory_compliance_calendar(request):
    """Read-only cross-scheme due-date calendar over StatutoryReturn (no new model). Groups returns
    into Overdue / Pending / Filed / Settled buckets; supports the same scheme/status GET filters as
    the return list. Grouped (not paginated) since it's a calendar overview."""
    # No select_related — the calendar rows render only scalar fields, never cycle/employee.
    qs = StatutoryReturn.objects.filter(tenant=request.tenant).order_by("due_date", "scheme")
    scheme = request.GET.get("scheme", "").strip()
    if scheme:
        qs = qs.filter(scheme=scheme)
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)
    buckets = {"overdue": [], "pending": [], "filed": [], "settled": []}
    for r in qs:
        if r.is_overdue:
            buckets["overdue"].append(r)
        elif r.status == "pending":
            buckets["pending"].append(r)
        elif r.status == "filed":
            buckets["filed"].append(r)
        else:  # paid / late — settled (a "late" row is paid-but-late, flagged in the template)
            buckets["settled"].append(r)
    # An ordered list of buckets so the template iterates directly (no custom dict-lookup filter).
    bucket_list = [
        {"label": "Overdue", "icon": "alarm-clock", "tone": "red", "rows": buckets["overdue"]},
        {"label": "Pending", "icon": "hourglass", "tone": "amber", "rows": buckets["pending"]},
        {"label": "Filed", "icon": "file-check", "tone": "info", "rows": buckets["filed"]},
        {"label": "Settled", "icon": "check-circle", "tone": "green", "rows": buckets["settled"]},
    ]
    return render(request, "hrm/statutory/compliance_calendar.html", {
        "bucket_list": bucket_list,
        "scheme_choices": StatutoryReturn.SCHEME_CHOICES,
        "status_choices": StatutoryReturn.STATUS_CHOICES,
    })
