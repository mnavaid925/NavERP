from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from apps.quality.models.DataIntegrity.AuditTrailReviews import AuditTrailReview
from apps.quality.models.DataIntegrity.DataIntegrityAssessments import DataIntegrityAssessment
from apps.quality.models.DataIntegrity.ElectronicRecordPolicies import ElectronicRecordPolicy
from apps.quality.models.DataIntegrity.SystemChangeControls import SystemChangeControl
from apps.quality.views._common import quality_scope


@login_required
def data_integrity_dashboard(request):
    today = timezone.now().date()

    policies_qs = quality_scope(ElectronicRecordPolicy.objects.all(), request)
    assessments_qs = quality_scope(DataIntegrityAssessment.objects.all(), request)
    reviews_qs = quality_scope(AuditTrailReview.objects.all(), request)
    changes_qs = quality_scope(SystemChangeControl.objects.all(), request)

    policy_stats = policies_qs.aggregate(
        total=Count("id"),
        part11=Count("id", filter=Q(is_part_11_regulated=True)),
        active=Count("id", filter=Q(status="active")),
    )
    total_policies_count = policy_stats["total"]
    part11_policies_count = policy_stats["part11"]

    assessment_stats = assessments_qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status__in=["draft", "in_assessment", "remediation_pending"])),
        critical=Count("id", filter=Q(overall_risk_level__in=["high", "critical"])),
        overdue=Count(
            "id",
            filter=Q(next_review_due__lt=today) & ~Q(status="approved"),
        ),
    )
    active_assessments_count = assessment_stats["active"]
    critical_risk_assessments_count = assessment_stats["critical"]
    overdue_assessments_count = assessment_stats["overdue"]

    review_stats = reviews_qs.aggregate(
        total=Count("id"),
        anomalies=Count("id", filter=Q(anomaly_severity__in=["major", "critical"])),
    )
    total_reviews_count = review_stats["total"]
    anomaly_reviews_count = review_stats["anomalies"]

    change_stats = changes_qs.aggregate(
        open_changes=Count(
            "id",
            filter=~Q(status__in=["implemented_closed", "rejected", "cancelled"]),
        ),
        emergency=Count("id", filter=Q(change_priority="emergency")),
    )
    open_changes_count = change_stats["open_changes"]
    emergency_changes_count = change_stats["emergency"]

    recent_policies = policies_qs.select_related("system", "system_owner")[:5]
    recent_assessments = assessments_qs.select_related("system", "lead_assessor")[:5]
    recent_reviews = reviews_qs.select_related("system", "reviewer")[:5]
    recent_changes = changes_qs.select_related("system", "requestor")[:5]

    context = {
        "total_policies_count": total_policies_count,
        "part11_policies_count": part11_policies_count,
        "active_assessments_count": active_assessments_count,
        "critical_risk_assessments_count": critical_risk_assessments_count,
        "overdue_assessments_count": overdue_assessments_count,
        "total_reviews_count": total_reviews_count,
        "anomaly_reviews_count": anomaly_reviews_count,
        "open_changes_count": open_changes_count,
        "emergency_changes_count": emergency_changes_count,
        "recent_policies": recent_policies,
        "recent_assessments": recent_assessments,
        "recent_reviews": recent_reviews,
        "recent_changes": recent_changes,
    }
    return render(
        request,
        "quality/data_integrity/data_integrity_dashboard.html",
        context,
    )
