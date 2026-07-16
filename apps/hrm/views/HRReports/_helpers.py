"""HRM 3.28 HR Reports — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    SeparationCase,
)
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._common import _date
from apps.hrm.views._helpers import _parse_iso_date


def _dept_choices(tenant):
    if tenant is None:
        return OrgUnit.objects.none()
    return OrgUnit.objects.filter(tenant=tenant, kind="department").order_by("name")


def _report_department(request, tenant):
    """Resolve ?department to a tenant-scoped department OrgUnit, or None (never trust the raw pk).
    Uses isdecimal() (not isdigit(), which accepts Unicode superscripts like "²" that int() rejects)
    + a length cap so a crafted ?department can't reach int() and raise a 500."""
    pk = (request.GET.get("department") or "").strip()
    if tenant is not None and pk.isdecimal() and len(pk) <= 18:
        return OrgUnit.objects.filter(tenant=tenant, kind="department", pk=int(pk)).first()
    return None


def _report_period(request):
    """(date_from, date_to) from ?date_from/?date_to, defaulting to the trailing 12 months."""
    today = timezone.localdate()
    date_to = _parse_iso_date(request.GET.get("date_to", "")) or today
    date_from = _parse_iso_date(request.GET.get("date_from", "")) or (date_to - timedelta(days=365))
    if date_from > date_to:  # a nonsensical range yields an empty (not crashing) report
        date_from = date_to
    return date_from, date_to


def _month_end(today, months_ago):
    """Last calendar day of the month `months_ago` months before `today` (no calendar import)."""
    total = today.year * 12 + (today.month - 1) - months_ago
    y, m = divmod(total, 12)
    m += 1
    nxt = _date(y + 1, 1, 1) if m == 12 else _date(y, m + 1, 1)
    return nxt - timedelta(days=1)


def _age(dob, as_of):
    if not dob:
        return None
    return as_of.year - dob.year - ((as_of.month, as_of.day) < (dob.month, dob.day))


def _tenure_band(days):
    if days is None:
        return "Unknown"
    years = days / 365.25
    if years < 1:
        return "<1 yr"
    if years < 3:
        return "1-2 yrs"
    if years < 6:
        return "3-5 yrs"
    if years < 11:
        return "6-10 yrs"
    return "10+ yrs"


def _age_band(years):
    if years is None:
        return "Unknown"
    for cut, label in ((25, "<25"), (35, "25-34"), (45, "35-44"), (55, "45-54"), (65, "55-64")):
        if years < cut:
            return label
    return "65+"


def _headcount_at(tenant, as_of):
    """Approx active headcount as of a date: hired on/before the date minus anyone separated by it."""
    hired = EmployeeProfile.objects.filter(tenant=tenant, employment__hired_on__lte=as_of).count()
    separated = (SeparationCase.objects.filter(tenant=tenant, actual_last_working_day__lte=as_of)
                 .values("employee_id").distinct().count())
    return max(0, hired - separated)
