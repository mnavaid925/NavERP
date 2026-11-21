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
from apps.quality.forms.ProcessValidation.ComputerSystemValidations import ComputerSystemValidationForm
from apps.quality.models.ProcessValidation.ComputerSystemValidations import ComputerSystemValidation
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def computer_system_validation_list(request):
    qs = quality_scope(ComputerSystemValidation.objects.all(), request).select_related(
        "system_owner", "quality_lead", "validation_protocol"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(system_name__icontains=q)
            | Q(version_release__icontains=q)
            | Q(vendor_name__icontains=q)
            | Q(description__icontains=q)
        )

    gamp_filter = request.GET.get("gamp", "").strip()
    if gamp_filter:
        qs = qs.filter(gamp_category=gamp_filter)

    gxp_filter = request.GET.get("gxp", "").strip()
    if gxp_filter:
        qs = qs.filter(gxp_impact=gxp_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    approach_filter = request.GET.get("approach", "").strip()
    if approach_filter:
        qs = qs.filter(validation_approach=approach_filter)

    base_tenant_qs = ComputerSystemValidation.objects.filter(tenant=request.tenant)
    today = datetime.date.today()
    stats = base_tenant_qs.aggregate(
        validated_count=Count("id", filter=Q(status="validated_live")),
        in_qual_count=Count("id", filter=Q(status__in=["planning", "in_qualification"])),
        review_due_count=Count("id", filter=Q(next_review_due__lt=today) & ~Q(status="decommissioned")),
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
        "computer_systems": page_obj,
        "total_count": total_count,
        "validated_count": stats["validated_count"],
        "in_qual_count": stats["in_qual_count"],
        "review_due_count": stats["review_due_count"],
        "gamp_choices": ComputerSystemValidation.GAMP_CATEGORY_CHOICES,
        "gxp_choices": ComputerSystemValidation.GXP_IMPACT_CHOICES,
        "status_choices": ComputerSystemValidation.STATUS_CHOICES,
        "approach_choices": ComputerSystemValidation.VALIDATION_APPROACH_CHOICES,
        "search_query": q,
        "query_string": query_params.urlencode(),
    }
    return render(request, "quality/processvalidation/computer_system_validation/list.html", context)


@login_required
def computer_system_validation_detail(request, pk):
    computer_system = quality_object(
        request,
        ComputerSystemValidation,
        pk,
        select_related=(
            "system_owner",
            "quality_lead",
            "validation_protocol",
            "urs_document",
            "vsr_document",
            "risk_assessment",
        ),
    )
    context = {
        "computer_system": computer_system,
        "is_detail": True,
    }
    return render(request, "quality/processvalidation/computer_system_validation/detail.html", context)


@login_required
def computer_system_validation_create(request):
    if request.method == "POST":
        form = ComputerSystemValidationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Computer System {obj.number} ({obj.system_name}) registered successfully.")
            return redirect("quality:computer_system_validation_detail", pk=obj.pk)
    else:
        form = ComputerSystemValidationForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
        "computer_system": None,
    }
    return render(request, "quality/processvalidation/computer_system_validation/form.html", context)


@login_required
def computer_system_validation_edit(request, pk):
    computer_system = quality_object(request, ComputerSystemValidation, pk)
    if request.method == "POST":
        form = ComputerSystemValidationForm(request.POST, instance=computer_system, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Computer System {obj.number} updated successfully.")
            return redirect("quality:computer_system_validation_detail", pk=obj.pk)
    else:
        form = ComputerSystemValidationForm(instance=computer_system, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "computer_system": computer_system,
    }
    return render(request, "quality/processvalidation/computer_system_validation/form.html", context)


@login_required
@require_POST
def computer_system_validation_delete(request, pk):
    computer_system = quality_object(request, ComputerSystemValidation, pk)
    num = computer_system.number
    write_audit_log(request.user, computer_system, "delete", tenant=request.tenant)
    computer_system.delete()
    messages.success(request, f"Computer System {num} deleted successfully.")
    return redirect("quality:computer_system_validation_list")


@login_required
def computer_system_validation_export(request):
    qs = quality_scope(ComputerSystemValidation.objects.all(), request).select_related(
        "system_owner", "quality_lead", "validation_protocol"
    )

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="computer_systems.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Number",
        "System Name",
        "Version",
        "Vendor",
        "GAMP Category",
        "GxP Impact",
        "Approach",
        "Hosting",
        "Part 11 Compliant",
        "Traceability",
        "URS Count",
        "Tests Count",
        "Deviations",
        "Status",
        "Validated Date",
        "Next Review Due",
        "System Owner",
        "QA Lead",
    ])

    for s in qs:
        writer.writerow([
            _csv_safe(s.number),
            _csv_safe(s.system_name),
            _csv_safe(s.version_release),
            _csv_safe(s.vendor_name),
            _csv_safe(s.get_gamp_category_display()),
            _csv_safe(s.get_gxp_impact_display()),
            _csv_safe(s.get_validation_approach_display()),
            _csv_safe(s.get_hosting_model_display()),
            "Yes" if s.is_part_11_compliant else "No",
            _csv_safe(s.get_traceability_status_display()),
            s.urs_requirements_count,
            s.test_scripts_count,
            s.deviations_found_count,
            _csv_safe(s.get_status_display()),
            _csv_safe(s.validated_date),
            _csv_safe(s.next_review_due),
            _csv_safe(s.system_owner.get_full_name() if s.system_owner else ""),
            _csv_safe(s.quality_lead.get_full_name() if s.quality_lead else ""),
        ])

    return response
