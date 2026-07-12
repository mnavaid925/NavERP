"""HRM 3.32 Analytics Dashboard — the compute layer.

Every figure surfaced by an ``HRDashboardWidget`` is a **read-only aggregation** over the existing
HRM models (EmployeeProfile / Employment / SeparationCase / LeaveRequest / AttendanceRecord /
Payslip / JobRequisition / JobApplication / PerformanceReview / Designation). Nothing is stored —
dashboards compute live on each render. Centralizing the queries here keeps the views thin and makes
the metrics unit-testable in isolation.

Import direction: this module imports ``models`` (+ ``apps.core.models.OrgUnit``) — ``models.py``
never imports this one (it owns only the field choice lists). That one-way edge avoids a circular
import. The three shared helpers (``_turnover_rate`` / ``_headcount_trend_series`` /
``_present_absent_counts``) plus ``_month_end`` / ``_tenure_band`` / ``_headcount_at`` are kept
self-contained here (mirroring the equivalents in ``views.py``) rather than imported from ``views.py``
— the reverse import (views imports analytics) is the established one-way edge, so views cannot be
imported here without a cycle. The derived 3.32 views import these from THIS module.

Widget result contract (``compute_widget``):
  * scalar -> {kind, value(float), display(str), max(float), pct(int 0-100)}
  * series -> {kind, labels[str], data[number]}
  * table  -> {kind, columns[str], rows[list]}
"""
import bisect
from datetime import date as _date, timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from .models import (
    APPLICATION_STAGE_CHOICES, AttendanceRecord, EmployeeProfile,
    EmployeeSalaryStructure, JobApplication, JobRequisition, LeaveRequest, Payslip,
    PerformanceReview, SeparationCase, WIDGET_METRIC_CHOICES,
)

_ATT_NON_WORKING = ("holiday", "on_leave")
_TENURE_POINTS = {"<1 yr": 30, "1-2 yrs": 20, "3-5 yrs": 10, "6-10 yrs": 5, "10+ yrs": 0, "Unknown": 15}


# ---------------------------------------------------------------------------
# Formatting helpers (return display strings; keep raw numbers separate)
# ---------------------------------------------------------------------------

def _money(v):
    return "${:,.0f}".format(float(v or 0))


def _num(v):
    return "{:,}".format(int(v or 0))


def _pct(v):
    return "{:.1f}%".format(float(v or 0))


def _years(v):
    return "{:.1f}".format(float(v or 0))


# ---------------------------------------------------------------------------
# Date-window selector — HR data is coarse-grained (monthly headcount/attrition,
# payroll cycles), so buckets are wider than CRM's and bounds are plain dates
# (every HRM aggregation filters DateFields). ``end`` is always today (never None).
# ---------------------------------------------------------------------------

def range_bounds(key):
    today = timezone.localdate()
    if key == "last_30":
        return today - timedelta(days=30), today
    if key == "last_90":
        return today - timedelta(days=90), today
    if key == "last_180":
        return today - timedelta(days=180), today
    if key == "last_365":
        return today - timedelta(days=365), today
    if key == "ytd":
        return _date(today.year, 1, 1), today
    return None, today  # "all"


def _since(qs, field, start):
    return qs.filter(**{f"{field}__gte": start}) if start is not None else qs


# ---------------------------------------------------------------------------
# Self-contained low-level helpers (mirror views.py, kept here to avoid a
# views<->analytics import cycle).
# ---------------------------------------------------------------------------

def _month_end(today, months_ago):
    """Last calendar day of the month ``months_ago`` months before ``today``."""
    total = today.year * 12 + (today.month - 1) - months_ago
    y, m = divmod(total, 12)
    m += 1
    nxt = _date(y + 1, 1, 1) if m == 12 else _date(y, m + 1, 1)
    return nxt - timedelta(days=1)


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


def _headcount_at(tenant, as_of):
    """Approx active headcount as of a date: hired on/before minus anyone separated by it."""
    hired = EmployeeProfile.objects.filter(tenant=tenant, employment__hired_on__lte=as_of).count()
    separated = (SeparationCase.objects.filter(tenant=tenant, actual_last_working_day__lte=as_of)
                 .values("employee_id").distinct().count())
    return max(0, hired - separated)


# ---------------------------------------------------------------------------
# Shared derived helpers (also imported by the 3.32 derived views).
# ---------------------------------------------------------------------------

def _turnover_rate(tenant, date_from, date_to, seps_count=None):
    """Annualized turnover % over [date_from, date_to]. Denominator is the avg of point-in-time
    headcount at each end. Documented pre-existing simplification (carried from attrition_report):
    the headcount denominator is always TENANT-WIDE, never department-filtered."""
    if seps_count is None:
        seps_count = (SeparationCase.objects.filter(
            tenant=tenant, actual_last_working_day__gte=date_from, actual_last_working_day__lte=date_to)
            .values("employee_id").distinct().count())
    avg_hc = (_headcount_at(tenant, date_from) + _headcount_at(tenant, date_to)) / 2
    days = max(1, (date_to - date_from).days)
    return round((seps_count / avg_hc) * (365 / days) * 100, 1) if avg_hc else 0.0


def _headcount_trend_series(tenant, end_date, months=12):
    """(labels, values) of point-in-time headcount at each of the last ``months`` month-ends.
    Two queries + bisect (no per-month query)."""
    hire_dates = sorted(EmployeeProfile.objects.filter(
        tenant=tenant, employment__hired_on__isnull=False)
        .values_list("employment__hired_on", flat=True))
    sep_dates = sorted(SeparationCase.objects.filter(
        tenant=tenant, actual_last_working_day__isnull=False)
        .values_list("actual_last_working_day", flat=True))
    labels, values = [], []
    for i in range(months - 1, -1, -1):
        m_end = _month_end(end_date, i)
        hired = bisect.bisect_right(hire_dates, m_end)
        separated = bisect.bisect_right(sep_dates, m_end)
        labels.append(m_end.strftime("%b %Y"))
        values.append(max(0, hired - separated))
    return labels, values


def _present_absent_counts(tenant, date_from, date_to, dept=None):
    """(absent_count, tracked_count) over [date_from, date_to]; tracked excludes holiday/on-leave."""
    qs = AttendanceRecord.objects.filter(tenant=tenant, date__gte=date_from, date__lte=date_to)
    if dept is not None:
        qs = qs.filter(employee__employment__org_unit=dept)
    counts = {r["status"]: r["c"] for r in qs.values("status").annotate(c=Count("id"))}
    tracked = sum(counts.values()) - counts.get("holiday", 0) - counts.get("on_leave", 0)
    return counts.get("absent", 0), tracked


def _attrition_risk_scores(tenant, dept=None):
    """Transparent, documented weighted-sum attrition-risk heuristic (0-100, higher = more risk) per
    ACTIVE employee. NOT an ML model. 5 queries + one bounded Python loop (no N+1).

    Weights: tenure 0-30, attendance 0-25, leave 0-20, probation 0-15, review-gap 0-10."""
    today = timezone.localdate()
    window_start = today - timedelta(days=90)
    emps = (EmployeeProfile.objects.filter(tenant=tenant, employment__status="active")
            .select_related("party", "employment", "employment__org_unit"))
    if dept is not None:
        emps = emps.filter(employment__org_unit=dept)
    emps = list(emps)
    if not emps:
        return []
    emp_ids = [e.pk for e in emps]

    # 1 query: attendance status counts (for absence rate)
    att = {}
    for r in (AttendanceRecord.objects.filter(
            tenant=tenant, employee_id__in=emp_ids, date__gte=window_start, date__lte=today)
            .values("employee_id", "status").annotate(c=Count("id"))):
        att.setdefault(r["employee_id"], {})[r["status"]] = r["c"]

    # 1 query: checked-in punches (late rate, minute-of-day compare in Python, mirrors is_late())
    late = {}
    for r in (AttendanceRecord.objects.filter(
            tenant=tenant, employee_id__in=emp_ids, date__gte=window_start, date__lte=today,
            check_in__isnull=False)
            .values("employee_id", "check_in", "shift__start_time", "shift__grace_minutes")):
        d = late.setdefault(r["employee_id"], {"late": 0, "total": 0})
        d["total"] += 1
        st, ci = r["shift__start_time"], r["check_in"]
        if st is not None and ci is not None:
            if (ci.hour * 60 + ci.minute) > (st.hour * 60 + st.minute) + (r["shift__grace_minutes"] or 0):
                d["late"] += 1

    # 1 query: recent leave requests
    leave = {r["employee_id"]: r["c"] for r in LeaveRequest.objects.filter(
        tenant=tenant, employee_id__in=emp_ids, status__in=("approved", "pending"),
        start_date__gte=window_start).values("employee_id").annotate(c=Count("id"))}

    # 1 query: employees with a recent completed review (membership set)
    reviewed = set(PerformanceReview.objects.filter(
        tenant=tenant, status__in=("shared", "acknowledged"),
        submitted_at__date__gte=today - timedelta(days=365))
        .values_list("subject_id", flat=True).distinct())

    out = []
    for e in emps:
        hired = e.employment.hired_on if e.employment_id else None
        tenure_days = (today - hired).days if hired else None
        tenure_pts = _TENURE_POINTS[_tenure_band(tenure_days)]

        acounts = att.get(e.pk, {})
        tracked = sum(acounts.values()) - acounts.get("holiday", 0) - acounts.get("on_leave", 0)
        absence_rate = round(acounts.get("absent", 0) / tracked * 100, 1) if tracked else 0.0
        lc = late.get(e.pk, {"late": 0, "total": 0})
        late_rate = round(lc["late"] / lc["total"] * 100, 1) if lc["total"] else 0.0
        attendance_pts = min(25, round(absence_rate * 0.8 + late_rate * 0.4))

        recent_leave = leave.get(e.pk, 0)
        leave_pts = min(20, recent_leave * 4)

        if e.confirmed_on:
            prob_pts = 0
        elif e.probation_end_date and today <= e.probation_end_date <= today + timedelta(days=30):
            prob_pts = 15
        elif e.probation_end_date and today <= e.probation_end_date <= today + timedelta(days=90):
            prob_pts = 8
        else:
            prob_pts = 0

        review_pts = 0 if e.pk in reviewed else 10
        score = min(100, tenure_pts + attendance_pts + leave_pts + prob_pts + review_pts)
        band = "Low" if score < 25 else "Medium" if score < 50 else "High" if score < 75 else "Critical"
        out.append({
            "employee": e.party.name if e.party_id else str(e),
            "employee_id": e.pk,
            "department_name": (e.employment.org_unit.name
                                if (e.employment_id and e.employment.org_unit_id) else "Unassigned"),
            "tenure_years": round(tenure_days / 365.25, 1) if tenure_days is not None else None,
            "absence_rate_pct": absence_rate, "late_rate_pct": late_rate,
            "recent_leave_count": recent_leave, "probation_flag": prob_pts > 0,
            "no_recent_review": e.pk not in reviewed, "score": score, "band": band,
        })
    return out


# ===========================================================================
# Widget metric resolvers — each takes (tenant, start, end), returns a partial
# result dict (kind/max/pct are added by compute_widget). start may be None ("all").
# ===========================================================================

# --- scalar (KPI card / gauge) ---------------------------------------------

def _r_kpi_headcount(tenant, start, end):
    n = EmployeeProfile.objects.filter(tenant=tenant, employment__status="active").count()
    return {"value": float(n), "display": _num(n)}


def _r_kpi_attrition_rate(tenant, start, end):
    rate = _turnover_rate(tenant, start or (end - timedelta(days=365)), end)
    return {"value": float(rate), "display": _pct(rate)}


def _r_kpi_avg_tenure(tenant, start, end):
    today = timezone.localdate()
    hired = EmployeeProfile.objects.filter(
        tenant=tenant, employment__status="active", employment__hired_on__isnull=False
    ).values_list("employment__hired_on", flat=True)
    tenures = [(today - h).days / 365.25 for h in hired]
    avg = round(sum(tenures) / len(tenures), 1) if tenures else 0.0
    return {"value": float(avg), "display": _years(avg)}


def _r_kpi_gross_payroll(tenant, start, end):
    qs = _since(Payslip.objects.filter(tenant=tenant, cycle__pay_date__lte=end), "cycle__pay_date", start)
    v = qs.aggregate(s=Sum("gross_pay"))["s"] or 0
    if not v:  # fallback: monthly run-rate from active salary structures (mirrors cost_report estimate)
        annual = (EmployeeSalaryStructure.objects.filter(tenant=tenant, status="active")
                  .aggregate(s=Sum("annual_ctc_amount"))["s"] or 0)
        v = (annual / 12) if annual else 0
    return {"value": float(v), "display": _money(v)}


def _r_kpi_absenteeism_rate(tenant, start, end):
    absent, tracked = _present_absent_counts(tenant, start or (end - timedelta(days=90)), end)
    rate = round(absent / tracked * 100, 1) if tracked else 0.0
    return {"value": float(rate), "display": _pct(rate)}


def _r_kpi_open_reqs(tenant, start, end):
    n = JobRequisition.objects.filter(tenant=tenant, status__in=("approved", "posted")).count()
    return {"value": float(n), "display": _num(n)}


def _r_kpi_pending_leave(tenant, start, end):
    n = LeaveRequest.objects.filter(tenant=tenant, status="pending").count()
    return {"value": float(n), "display": _num(n)}


def _r_kpi_gender_diversity(tenant, start, end):
    counts = {r["gender"]: r["c"] for r in EmployeeProfile.objects.filter(
        tenant=tenant, employment__status="active").values("gender").annotate(c=Count("id"))}
    total = sum(counts.values())
    pct = round(counts.get("female", 0) / total * 100, 1) if total else 0.0
    return {"value": float(pct), "display": _pct(pct)}


def _r_kpi_avg_attrition_risk(tenant, start, end):
    scores = [s["score"] for s in _attrition_risk_scores(tenant)]
    avg = round(sum(scores) / len(scores), 1) if scores else 0.0
    return {"value": float(avg), "display": _years(avg)}


# --- series (bar / line / pie / doughnut) ----------------------------------

def _r_headcount_trend(tenant, start, end):
    labels, data = _headcount_trend_series(tenant, end, months=12)
    return {"labels": labels, "data": data}


def _r_attrition_by_department(tenant, start, end):
    qs = _since(SeparationCase.objects.filter(tenant=tenant, actual_last_working_day__lte=end),
                "actual_last_working_day", start)
    rows = (qs.values("employee__employment__org_unit__name").annotate(c=Count("id")).order_by("-c"))
    labels = [r["employee__employment__org_unit__name"] or "Unassigned" for r in rows]
    return {"labels": labels, "data": [r["c"] for r in rows]}


def _r_gender_split(tenant, start, end):
    labels_map = dict(EmployeeProfile.GENDER_CHOICES)
    counts = {r["gender"]: r["c"] for r in EmployeeProfile.objects.filter(
        tenant=tenant, employment__status="active").values("gender").annotate(c=Count("id"))}
    labels, data = [], []
    for val, label in EmployeeProfile.GENDER_CHOICES:
        if counts.get(val):
            labels.append(label)
            data.append(counts[val])
    if counts.get("", 0):
        labels.append("Not specified")
        data.append(counts[""])
    return {"labels": labels, "data": data}


def _r_leave_by_type(tenant, start, end):
    qs = _since(LeaveRequest.objects.filter(tenant=tenant, status="approved", start_date__lte=end),
                "start_date", start)
    rows = qs.values("leave_type__name").annotate(d=Sum("days")).order_by("-d")
    return {"labels": [r["leave_type__name"] or "-" for r in rows],
            "data": [float(r["d"] or 0) for r in rows]}


def _r_hiring_funnel(tenant, start, end):
    qs = _since(JobApplication.objects.filter(tenant=tenant, applied_at__date__lte=end),
                "applied_at__date", start)
    counts = {r["stage"]: r["c"] for r in qs.values("stage").annotate(c=Count("id"))}
    labels, data = [], []
    for val, label in APPLICATION_STAGE_CHOICES:
        labels.append(label)
        data.append(counts.get(val, 0))
    return {"labels": labels, "data": data}


def _r_payroll_cost_by_department(tenant, start, end):
    qs = _since(Payslip.objects.filter(tenant=tenant, cycle__pay_date__lte=end), "cycle__pay_date", start)
    rows = (qs.values("employee__employment__org_unit__name").annotate(s=Sum("gross_pay")).order_by("-s"))
    return {"labels": [r["employee__employment__org_unit__name"] or "Unassigned" for r in rows],
            "data": [float(r["s"] or 0) for r in rows]}


# --- table -----------------------------------------------------------------

def _r_top_attrition_risk_employees(tenant, start, end):
    scores = sorted(_attrition_risk_scores(tenant), key=lambda s: s["score"], reverse=True)[:10]
    rows = [[s["employee"], s["department_name"],
             (_years(s["tenure_years"]) if s["tenure_years"] is not None else "-"),
             s["score"], s["band"]] for s in scores]
    return {"columns": ["Employee", "Department", "Tenure (yrs)", "Risk Score", "Risk Band"], "rows": rows}


# ---------------------------------------------------------------------------
# Registry + dispatcher (mirrors apps/crm/analytics.py).
# ---------------------------------------------------------------------------

SCALAR_CHARTS = ["kpi", "gauge"]
SERIES_CHARTS = ["bar", "line", "pie", "doughnut"]
TABLE_CHARTS = ["table"]

WIDGET_METRICS = {
    "kpi_headcount": {"kind": "scalar", "charts": SCALAR_CHARTS, "resolver": _r_kpi_headcount},
    "kpi_attrition_rate": {"kind": "scalar", "charts": SCALAR_CHARTS, "resolver": _r_kpi_attrition_rate, "intrinsic_max": 100},
    "kpi_avg_tenure": {"kind": "scalar", "charts": SCALAR_CHARTS, "resolver": _r_kpi_avg_tenure},
    "kpi_gross_payroll": {"kind": "scalar", "charts": SCALAR_CHARTS, "resolver": _r_kpi_gross_payroll},
    "kpi_absenteeism_rate": {"kind": "scalar", "charts": SCALAR_CHARTS, "resolver": _r_kpi_absenteeism_rate, "intrinsic_max": 100},
    "kpi_open_reqs": {"kind": "scalar", "charts": SCALAR_CHARTS, "resolver": _r_kpi_open_reqs},
    "kpi_pending_leave": {"kind": "scalar", "charts": SCALAR_CHARTS, "resolver": _r_kpi_pending_leave},
    "kpi_gender_diversity": {"kind": "scalar", "charts": SCALAR_CHARTS, "resolver": _r_kpi_gender_diversity, "intrinsic_max": 100},
    "kpi_avg_attrition_risk": {"kind": "scalar", "charts": SCALAR_CHARTS, "resolver": _r_kpi_avg_attrition_risk, "intrinsic_max": 100},
    "headcount_trend": {"kind": "series", "charts": SERIES_CHARTS, "resolver": _r_headcount_trend},
    "attrition_by_department": {"kind": "series", "charts": SERIES_CHARTS, "resolver": _r_attrition_by_department},
    "gender_split": {"kind": "series", "charts": SERIES_CHARTS, "resolver": _r_gender_split},
    "leave_by_type": {"kind": "series", "charts": SERIES_CHARTS, "resolver": _r_leave_by_type},
    "hiring_funnel": {"kind": "series", "charts": SERIES_CHARTS, "resolver": _r_hiring_funnel},
    "payroll_cost_by_department": {"kind": "series", "charts": SERIES_CHARTS, "resolver": _r_payroll_cost_by_department},
    "top_attrition_risk_employees": {"kind": "table", "charts": TABLE_CHARTS, "resolver": _r_top_attrition_risk_employees},
}

# Sanity: every declared metric choice has a resolver.
assert {k for k, _ in WIDGET_METRIC_CHOICES} == set(WIDGET_METRICS), "WIDGET_METRICS out of sync with WIDGET_METRIC_CHOICES"


def allowed_charts(metric):
    """Chart types valid for a metric (used by the widget form's clean())."""
    meta = WIDGET_METRICS.get(metric)
    return meta["charts"] if meta else []


def compute_widget(widget):
    """Compute a single widget live. Returns the normalized result dict (see module docstring)."""
    meta = WIDGET_METRICS.get(widget.metric)
    if not meta:
        return {"kind": "scalar", "value": 0, "display": "-", "error": "Unknown metric"}
    start, end = range_bounds(widget.date_range)
    result = meta["resolver"](widget.tenant, start, end)
    result["kind"] = meta["kind"]
    if meta["kind"] == "scalar":
        val = result.get("value") or 0
        target = float(widget.target_value) if widget.target_value is not None else None
        max_v = target or meta.get("intrinsic_max") or (val if val > 0 else 1)
        result["max"] = max_v
        result["pct"] = min(100, round(val / max_v * 100)) if max_v else 0
    return result
