from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, F
from django.shortcuts import render
from django.utils import timezone

from apps.quality.models.CustomerComplaints.ComplaintInvestigations import ComplaintInvestigation
from apps.quality.models.CustomerComplaints.CustomerComplaints import CustomerComplaint
from apps.quality.models.CustomerComplaints.FieldActions import FieldAction
from apps.quality.models.CustomerComplaints.RegulatoryReports import RegulatoryReport
from apps.quality.views._common import quality_scope


@login_required
def complaint_trending_dashboard(request):
    tenant = request.tenant
    now = timezone.now()
    year_start = now.date().replace(month=1, day=1)

    base_complaints = quality_scope(CustomerComplaint.objects.all(), request)
    total_complaints_ytd = base_complaints.filter(date_received__gte=year_start).count()
    open_complaints = base_complaints.exclude(status__in=["closed", "cancelled"]).count()
    reportable_adverse_events = base_complaints.filter(reportability="reportable_event").count()

    base_field_actions = quality_scope(FieldAction.objects.all(), request)
    active_field_recalls = base_field_actions.exclude(status__in=["closed_terminated", "cancelled"]).count()

    # Calculate average cycle time for closed complaints
    closed_dates = list(
        base_complaints.filter(status="closed", closed_at__isnull=False, date_received__isnull=False).values_list(
            "closed_at", "date_received"
        )
    )
    avg_cycle_days = (
        round(sum((ca.date() - dr).days for ca, dr in closed_dates) / len(closed_dates), 1)
        if closed_dates
        else 0.0
    )

    # Category distribution
    cat_counts = (
        base_complaints.exclude(complaint_category="")
        .values("complaint_category")
        .annotate(total=Count("id"))
        .order_by("-total")[:8]
    )
    category_distribution = [{"category": row["complaint_category"], "count": row["total"]} for row in cat_counts]

    # Severity distribution
    sev_counts = dict(
        base_complaints.values("severity").annotate(total=Count("id")).values_list("severity", "total")
    )
    severity_distribution = []
    for val, label in CustomerComplaint.SEVERITY_CHOICES:
        count = sev_counts.get(val, 0)
        css = CustomerComplaint.SEVERITY_CSS.get(val, "badge-slate")
        severity_distribution.append({
            "severity": val,
            "label": label,
            "count": count,
            "css": css,
        })

    # Intake channel stats
    chan_counts = dict(
        base_complaints.values("intake_channel").annotate(total=Count("id")).values_list("intake_channel", "total")
    )
    intake_channel_stats = []
    for val, label in CustomerComplaint.INTAKE_CHANNEL_CHOICES:
        intake_channel_stats.append({
            "channel": val,
            "label": label,
            "count": chan_counts.get(val, 0),
        })

    # Root cause Pareto from investigations
    base_invs = quality_scope(ComplaintInvestigation.objects.all(), request)
    rc_counts = (
        base_invs.values("root_cause_category")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    rc_dict = dict(ComplaintInvestigation.ROOT_CAUSE_CATEGORY_CHOICES)
    total_invs = sum(row["total"] for row in rc_counts) or 1
    root_cause_pareto = [
        {
            "cause": row["root_cause_category"],
            "label": rc_dict.get(row["root_cause_category"], row["root_cause_category"]),
            "count": row["total"],
            "percent": min(100, max(5, int((row["total"] / total_invs) * 100))),
        }
        for row in rc_counts
    ]

    # Upcoming statutory deadlines
    base_reports = quality_scope(RegulatoryReport.objects.all(), request)
    urgent_regulatory_deadlines = (
        base_reports.exclude(submission_status__in=["acknowledged", "withdrawn"])
        .select_related("complaint")
        .order_by("statutory_due_date")[:6]
    )

    # Active field actions
    active_recalls = (
        base_field_actions.exclude(status__in=["closed_terminated", "cancelled"])
        .order_by("-initiation_date")[:5]
    )

    context = {
        "total_complaints_ytd": total_complaints_ytd,
        "open_complaints": open_complaints,
        "reportable_adverse_events": reportable_adverse_events,
        "active_field_recalls": active_field_recalls,
        "avg_cycle_days": avg_cycle_days,
        "category_distribution": category_distribution,
        "severity_distribution": severity_distribution,
        "intake_channel_stats": intake_channel_stats,
        "root_cause_pareto": root_cause_pareto,
        "urgent_regulatory_deadlines": urgent_regulatory_deadlines,
        "active_recalls": active_recalls,
    }
    return render(
        request,
        "quality/customercomplaints/complaint_trending_dashboard.html",
        context,
    )
