"""HRM 3.11 Time Tracking — ProjectTimeReport views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    TimesheetEntry,
)
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._helpers import _parse_iso_date


@login_required
def project_time_report(request):
    """Per-``accounting.Project`` logged hours vs budget (derived, no model).
    Optional ``?date_from``/``?date_to`` bound by the entry date."""
    tenant = request.tenant
    rows = []
    date_from = _parse_iso_date(request.GET.get("date_from", "").strip())
    date_to = _parse_iso_date(request.GET.get("date_to", "").strip())
    if tenant is not None:
        qs = TimesheetEntry.objects.filter(tenant=tenant, project__isnull=False)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        # Alias the aggregates away from the `hours` field name — an annotation named `hours` would
        # shadow the field and make the second Sum("hours", ...) raise "hours is an aggregate".
        for d in (qs.values("project__number", "project__name", "project__budget_amount")
                  .annotate(logged=Sum("hours"), billable=Sum("hours", filter=Q(is_billable=True)))
                  .order_by("project__name")):
            rows.append({"number": d["project__number"], "name": d["project__name"],
                         "budget": d["project__budget_amount"] or Decimal("0"),
                         "hours": d["logged"] or Decimal("0"),
                         "billable_hours": d["billable"] or Decimal("0")})
    return render(request, "hrm/timetracking/project_time_report.html", {"rows": rows})
