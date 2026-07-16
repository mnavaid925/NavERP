"""HRM 3.27 Communication Hub — Celebrations views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.CommunicationHub._helpers import _days_until, _next_occurrence
from apps.hrm.models import (
    EmployeeProfile,
)
from apps.hrm.views.CommunicationHub._helpers import _days_until, _next_occurrence


@login_required
def celebrations(request):
    """Upcoming birthdays + work anniversaries — DERIVED (no model) from EmployeeProfile.date_of_birth
    and core.Employment.hired_on, mirroring org_chart's no-table, capped, Python-bucketed shape."""
    tenant = request.tenant
    try:
        window = int(request.GET.get("window", 30))
    except (TypeError, ValueError):
        window = 30
    window = max(1, min(window, 90))
    CAP = 500
    today = timezone.localdate()
    birthdays, anniversaries, capped = [], [], False
    if tenant is not None:
        emps = list(
            EmployeeProfile.objects.filter(tenant=tenant)
            .exclude(employment__status="terminated")
            .select_related("party", "employment", "employment__org_unit")[:CAP + 1])
        capped = len(emps) > CAP  # surface the truncation instead of silently dropping employees
        emps = emps[:CAP]
        for e in emps:
            dept = e.employment.org_unit.name if (e.employment_id and e.employment.org_unit_id) else "—"
            if e.date_of_birth:
                days = _days_until(e.date_of_birth, today)
                if days <= window:
                    birthdays.append({"emp": e, "dept": dept,
                                      "date": _next_occurrence(e.date_of_birth, today), "days": days})
            hired = e.employment.hired_on if e.employment_id else None
            if hired and hired <= today:
                occ = _next_occurrence(hired, today)
                days = (occ - today).days
                years = occ.year - hired.year
                if days <= window and years >= 1:
                    anniversaries.append({"emp": e, "dept": dept, "date": occ, "days": days, "years": years})
        birthdays.sort(key=lambda r: r["days"])
        anniversaries.sort(key=lambda r: r["days"])
    return render(request, "hrm/communication/celebrations.html", {
        "birthdays": birthdays, "anniversaries": anniversaries, "window": window,
        "capped": capped, "cap": CAP,
    })
