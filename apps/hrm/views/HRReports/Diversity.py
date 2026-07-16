"""HRM 3.28 HR Reports — Diversity views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.HRReports._helpers import _age, _age_band, _dept_choices, _report_department, _tenure_band
from apps.hrm.models import (
    EmployeeProfile,
)
from apps.hrm.views.HRReports.Ages import AGE_BANDS
from apps.hrm.views.HRReports.Tenures import TENURE_BANDS
from apps.hrm.views.HRReports._helpers import _age, _age_band, _dept_choices, _report_department, _tenure_band
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._helpers import _parse_iso_date


@tenant_admin_required
def diversity_report(request):
    tenant = request.tenant
    today = timezone.localdate()
    as_of = _parse_iso_date(request.GET.get("as_of", "")) or today
    dept = _report_department(request, tenant)
    ctx = {"as_of": as_of, "department": dept, "department_choices": _dept_choices(tenant),
           "total": 0, "avg_age": None, "avg_tenure": None, "by_gender": [], "by_age": [],
           "by_tenure": [], "crosstab": [], "genders": []}
    if tenant is not None:
        active = (EmployeeProfile.objects.filter(tenant=tenant, employment__status="active")
                  .select_related("employment", "employment__org_unit"))
        if dept:
            active = active.filter(employment__org_unit=dept)
        rows = list(active)
        total = len(rows)
        ctx["total"] = total
        gender_counts, age_counts = {}, {b: 0 for b in AGE_BANDS}
        tenure_counts, crosstab = {b: 0 for b in TENURE_BANDS}, {}
        ages, tenures, gender_labels = [], [], {g: lbl for g, lbl in EmployeeProfile.GENDER_CHOICES}
        gender_order = []
        for e in rows:
            glabel = gender_labels.get(e.gender, "Not Specified") if e.gender else "Not Specified"
            gender_counts[glabel] = gender_counts.get(glabel, 0) + 1
            if glabel not in gender_order:
                gender_order.append(glabel)
            age = _age(e.date_of_birth, as_of)
            if age is not None:
                ages.append(age)
            age_counts[_age_band(age)] += 1
            hired = e.employment.hired_on if e.employment else None
            td = (as_of - hired).days if hired else None
            if td is not None:
                tenures.append(td)
            tenure_counts[_tenure_band(td)] += 1
            unit = e.employment.org_unit.name if (e.employment and e.employment.org_unit_id) else "Unassigned"
            crosstab.setdefault(unit, {}).setdefault(glabel, 0)
            crosstab[unit][glabel] += 1
        ctx["avg_age"] = round(sum(ages) / len(ages), 1) if ages else None
        ctx["avg_tenure"] = round(sum(tenures) / len(tenures) / 365.25, 1) if tenures else None
        ctx["genders"] = gender_order
        ctx["by_gender"] = [{"name": g, "count": gender_counts[g],
                             "pct": round(gender_counts[g] / total * 100, 1) if total else 0}
                            for g in gender_order]
        ctx["by_age"] = [{"name": b, "count": age_counts[b]} for b in AGE_BANDS if age_counts[b]]
        ctx["by_tenure"] = [{"name": b, "count": tenure_counts[b]} for b in TENURE_BANDS if tenure_counts[b]]
        ctx["crosstab"] = [{"dept": u, "counts": [crosstab[u].get(g, 0) for g in gender_order],
                            "total": sum(crosstab[u].values())} for u in sorted(crosstab)]
    return render(request, "hrm/reports/diversity.html", ctx)
