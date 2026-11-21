import csv
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.quality.forms.ProcessValidation.CleaningValidations import CleaningValidationForm
from apps.quality.models.ProcessValidation.CleaningValidations import CleaningValidation
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def cleaning_validation_list(request):
    qs = quality_scope(CleaningValidation.objects.all(), request).select_related(
        "analytical_lead", "qa_approver", "validation_protocol", "cleaning_sop"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(equipment_train_tag__icontains=q)
            | Q(target_residue__icontains=q)
            | Q(cleaning_agent_used__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(cleaning_status=status_filter)

    method_filter = request.GET.get("method", "").strip()
    if method_filter:
        qs = qs.filter(analytical_method=method_filter)

    basis_filter = request.GET.get("basis", "").strip()
    if basis_filter:
        qs = qs.filter(calculation_basis=basis_filter)

    base_tenant_qs = CleaningValidation.objects.filter(tenant=request.tenant)
    today = datetime.date.today()
    stats = base_tenant_qs.aggregate(
        validated_count=Count("id", filter=Q(cleaning_status="validated_pass")),
        sampling_count=Count("id", filter=Q(cleaning_status__in=["sampling_in_progress", "analytical_testing"])),
        failed_count=Count("id", filter=Q(cleaning_status="failed_recleaning")),
        reval_due_count=Count("id", filter=Q(next_revalidation_date__lt=today) & ~Q(cleaning_status="expired")),
    )

    paginator = Paginator(qs, PAGE_SIZE)
    total_count = paginator.count
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    if "page" in query_params:
        query_params.pop("page")

    context = {
        "page_obj": page_obj,
        "cleaning_validations": page_obj,
        "total_count": total_count,
        "validated_count": stats["validated_count"],
        "sampling_count": stats["sampling_count"],
        "failed_count": stats["failed_count"],
        "reval_due_count": stats["reval_due_count"],
        "status_choices": CleaningValidation.CLEANING_STATUS_CHOICES,
        "method_choices": CleaningValidation.ANALYTICAL_METHOD_CHOICES,
        "basis_choices": CleaningValidation.CALCULATION_BASIS_CHOICES,
        "search_query": q,
        "query_string": query_params.urlencode(),
    }
    return render(request, "quality/processvalidation/cleaning_validation/list.html", context)


@login_required
def cleaning_validation_detail(request, pk):
    cleaning_validation = quality_object(
        request,
        CleaningValidation,
        pk,
        select_related=(
            "analytical_lead",
            "qa_approver",
            "validation_protocol",
            "cleaning_sop",
            "linked_deviation",
        ),
    )
    context = {
        "cleaning_validation": cleaning_validation,
        "is_detail": True,
    }
    return render(request, "quality/processvalidation/cleaning_validation/detail.html", context)


@login_required
def cleaning_validation_create(request):
    if request.method == "POST":
        form = CleaningValidationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Cleaning Validation Study {obj.number} created successfully.")
            return redirect("quality:cleaning_validation_detail", pk=obj.pk)
    else:
        form = CleaningValidationForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
        "cleaning_validation": None,
    }
    return render(request, "quality/processvalidation/cleaning_validation/form.html", context)


@login_required
def cleaning_validation_edit(request, pk):
    cleaning_validation = quality_object(request, CleaningValidation, pk)
    if request.method == "POST":
        form = CleaningValidationForm(request.POST, instance=cleaning_validation, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Cleaning Validation Study {obj.number} updated successfully.")
            return redirect("quality:cleaning_validation_detail", pk=obj.pk)
    else:
        form = CleaningValidationForm(instance=cleaning_validation, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "cleaning_validation": cleaning_validation,
    }
    return render(request, "quality/processvalidation/cleaning_validation/form.html", context)


@login_required
@require_POST
def cleaning_validation_delete(request, pk):
    cleaning_validation = quality_object(request, CleaningValidation, pk)
    num = cleaning_validation.number
    write_audit_log(request.user, cleaning_validation, "delete", tenant=request.tenant)
    cleaning_validation.delete()
    messages.success(request, f"Cleaning Validation Study {num} deleted successfully.")
    return redirect("quality:cleaning_validation_list")


@login_required
def cleaning_validation_export(request):
    qs = quality_scope(CleaningValidation.objects.all(), request).select_related(
        "analytical_lead", "qa_approver", "validation_protocol", "cleaning_sop"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(equipment_train_tag__icontains=q)
            | Q(target_residue__icontains=q)
            | Q(cleaning_agent_used__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(cleaning_status=status_filter)

    method_filter = request.GET.get("method", "").strip()
    if method_filter:
        qs = qs.filter(analytical_method=method_filter)

    basis_filter = request.GET.get("basis", "").strip()
    if basis_filter:
        qs = qs.filter(calculation_basis=basis_filter)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="cleaning_validations.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Number",
        "Title",
        "Equipment Train",
        "Target Residue",
        "Cleaning Agent",
        "Calculation Basis",
        "MACO (mg)",
        "Surface Area (cm2)",
        "Swab Limit (ug)",
        "Rinse Limit (ppm)",
        "Analytical Method",
        "Recovery %",
        "DHT (hours)",
        "CHT (hours)",
        "Visually Clean",
        "Status",
        "Next Revalidation",
        "Analytical Lead",
    ])

    for c in qs.iterator(chunk_size=1000):
        writer.writerow([
            _csv_safe(c.number),
            _csv_safe(c.title),
            _csv_safe(c.equipment_train_tag),
            _csv_safe(c.target_residue),
            _csv_safe(c.cleaning_agent_used),
            _csv_safe(c.get_calculation_basis_display()),
            c.calculated_maco_mg or "",
            c.total_surface_area_sqcm,
            c.calculated_swab_limit_ug or "",
            c.calculated_rinse_limit_ppm or "",
            _csv_safe(c.get_analytical_method_display()),
            c.method_recovery_percentage,
            c.dirty_hold_time_hours,
            c.clean_hold_time_hours,
            "Yes" if c.is_visually_clean else "No",
            _csv_safe(c.get_cleaning_status_display()),
            _csv_safe(c.next_revalidation_date),
            _csv_safe(c.analytical_lead.get_full_name() if c.analytical_lead else ""),
        ])

    return response
