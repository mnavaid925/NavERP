from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from apps.quality.models.RegulatorySubmissions.PostMarketSurveillanceReports import PostMarketSurveillanceReport
from apps.quality.models.RegulatorySubmissions.ProductRegistrations import ProductRegistration
from apps.quality.models.RegulatorySubmissions.RegulatoryCommitments import RegulatoryCommitment
from apps.quality.models.RegulatorySubmissions.RegulatorySubmissions import RegulatorySubmission
from apps.quality.views._common import quality_scope


@login_required
def regulatory_dashboard(request):
    submissions_qs = quality_scope(RegulatorySubmission.objects.all(), request)
    registrations_qs = quality_scope(ProductRegistration.objects.all(), request)
    commitments_qs = quality_scope(RegulatoryCommitment.objects.all(), request)
    pms_qs = quality_scope(PostMarketSurveillanceReport.objects.all(), request)

    today = timezone.now().date()

    total_submissions = submissions_qs.count()
    active_registrations = registrations_qs.filter(status="active").count()
    open_commitments = commitments_qs.filter(status__in=["open", "in_progress"]).count()
    overdue_commitments = commitments_qs.filter(
        Q(status="overdue") | (Q(status__in=["open", "in_progress"]) & Q(due_date__lt=today))
    ).count()
    pms_reports_count = pms_qs.count()

    recent_submissions = submissions_qs.select_related("target_authority").order_by("-created_at")[:5]
    expiring_registrations = (
        registrations_qs.filter(status__in=["active", "pending_renewal"], expiration_date__isnull=False)
        .order_by("expiration_date")[:5]
    )
    pending_commitments = (
        commitments_qs.filter(status__in=["open", "in_progress"])
        .select_related("regulatory_agency", "responsible_owner")
        .order_by("due_date")[:5]
    )
    recent_pms_reports = pms_qs.select_related("product_registration").order_by("-reporting_period_end")[:5]

    context = {
        "total_submissions": total_submissions,
        "active_registrations": active_registrations,
        "open_commitments": open_commitments,
        "overdue_commitments": overdue_commitments,
        "pms_reports_count": pms_reports_count,
        "recent_submissions": recent_submissions,
        "expiring_registrations": expiring_registrations,
        "pending_commitments": pending_commitments,
        "recent_pms_reports": recent_pms_reports,
    }
    return render(
        request,
        "quality/regulatory_submissions/regulatory_dashboard.html",
        context,
    )
