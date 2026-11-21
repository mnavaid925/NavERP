import datetime

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render

from apps.quality.models.ProcessValidation.CleaningValidations import CleaningValidation
from apps.quality.models.ProcessValidation.ComputerSystemValidations import ComputerSystemValidation
from apps.quality.models.ProcessValidation.ProcessCapabilityStudies import ProcessCapabilityStudy
from apps.quality.models.ProcessValidation.ValidationProtocols import ValidationProtocol


@login_required
def process_validation_dashboard(request):
    today = datetime.date.today()
    tenant = request.tenant

    protocol_stats = ValidationProtocol.objects.filter(tenant=tenant).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status__in=["in_review", "approved_for_execution", "in_execution"])),
        completed=Count("id", filter=Q(status__in=["execution_completed", "final_approved"])),
        overdue=Count("id", filter=Q(target_completion_date__lt=today) & ~Q(status__in=["final_approved", "rejected", "superseded"])),
        reval_overdue=Count("id", filter=Q(revalidation_due_date__lt=today) & ~Q(status__in=["rejected", "superseded"])),
    )

    capability_stats = ProcessCapabilityStudy.objects.filter(tenant=tenant).aggregate(
        total=Count("id"),
        capable=Count("id", filter=Q(capability_determination__in=["capable", "highly_capable"])),
        marginal=Count("id", filter=Q(capability_determination="marginally_capable")),
        incapable=Count("id", filter=Q(capability_determination="incapable")),
    )

    csv_stats = ComputerSystemValidation.objects.filter(tenant=tenant).aggregate(
        total=Count("id"),
        validated=Count("id", filter=Q(status="validated_live")),
        review_due=Count("id", filter=Q(next_review_due__lt=today) & ~Q(status="decommissioned")),
    )

    cleaning_stats = CleaningValidation.objects.filter(tenant=tenant).aggregate(
        total=Count("id"),
        validated=Count("id", filter=Q(cleaning_status="validated_pass")),
        active=Count("id", filter=Q(cleaning_status__in=["sampling_in_progress", "analytical_testing"])),
        reval_due=Count("id", filter=Q(next_revalidation_date__lt=today) & ~Q(cleaning_status="expired")),
    )

    total_overdue = (protocol_stats["reval_overdue"] or 0) + (csv_stats["review_due"] or 0) + (cleaning_stats["reval_due"] or 0)

    recent_protocols = ValidationProtocol.objects.filter(tenant=tenant).select_related(
        "lead_author", "department"
    ).order_by("-created_at")[:5]

    recent_studies = ProcessCapabilityStudy.objects.filter(tenant=tenant).select_related(
        "investigator"
    ).order_by("-created_at")[:5]

    recent_systems = ComputerSystemValidation.objects.filter(tenant=tenant).select_related(
        "system_owner", "quality_lead"
    ).order_by("-created_at")[:5]

    recent_cleaning = CleaningValidation.objects.filter(tenant=tenant).select_related(
        "analytical_lead"
    ).order_by("-created_at")[:5]

    context = {
        "total_protocols": protocol_stats["total"] or 0,
        "active_protocols": protocol_stats["active"] or 0,
        "completed_protocols": protocol_stats["completed"] or 0,
        "overdue_protocols": protocol_stats["overdue"] or 0,
        "total_studies": capability_stats["total"] or 0,
        "capable_studies": capability_stats["capable"] or 0,
        "marginal_studies": capability_stats["marginal"] or 0,
        "incapable_studies": capability_stats["incapable"] or 0,
        "total_systems": csv_stats["total"] or 0,
        "validated_systems": csv_stats["validated"] or 0,
        "total_cleaning": cleaning_stats["total"] or 0,
        "validated_cleaning": cleaning_stats["validated"] or 0,
        "overdue_revalidations": total_overdue,
        "recent_protocols": recent_protocols,
        "recent_studies": recent_studies,
        "recent_systems": recent_systems,
        "recent_cleaning": recent_cleaning,
    }
    return render(request, "quality/processvalidation/process_validation_dashboard.html", context)
