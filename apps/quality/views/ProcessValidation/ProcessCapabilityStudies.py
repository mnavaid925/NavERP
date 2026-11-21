import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.quality.forms.ProcessValidation.ProcessCapabilityStudies import ProcessCapabilityStudyForm
from apps.quality.models.ProcessValidation.ProcessCapabilityStudies import ProcessCapabilityStudy
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def process_capability_study_list(request):
    qs = quality_scope(ProcessCapabilityStudy.objects.all(), request).select_related(
        "investigator", "approved_by", "validation_protocol"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(parameter_name__icontains=q)
            | Q(process_name__icontains=q)
            | Q(equipment_tag__icontains=q)
            | Q(lot_number__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    determination_filter = request.GET.get("determination", "").strip()
    if determination_filter:
        qs = qs.filter(capability_determination=determination_filter)

    category_filter = request.GET.get("category", "").strip()
    if category_filter:
        qs = qs.filter(parameter_category=category_filter)

    base_tenant_qs = ProcessCapabilityStudy.objects.filter(tenant=request.tenant)
    stats = base_tenant_qs.aggregate(
        capable_count=Count("id", filter=Q(capability_determination__in=["capable", "highly_capable"])),
        marginal_count=Count("id", filter=Q(capability_determination="marginally_capable")),
        incapable_count=Count("id", filter=Q(capability_determination="incapable")),
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
        "capability_studies": page_obj,
        "total_count": total_count,
        "capable_count": stats["capable_count"],
        "marginal_count": stats["marginal_count"],
        "incapable_count": stats["incapable_count"],
        "status_choices": ProcessCapabilityStudy.STATUS_CHOICES,
        "determination_choices": ProcessCapabilityStudy.CAPABILITY_DETERMINATION_CHOICES,
        "category_choices": ProcessCapabilityStudy.PARAMETER_CATEGORY_CHOICES,
        "search_query": q,
        "query_string": query_params.urlencode(),
    }
    return render(request, "quality/processvalidation/process_capability_study/list.html", context)


@login_required
def process_capability_study_detail(request, pk):
    capability_study = quality_object(
        request,
        ProcessCapabilityStudy,
        pk,
        select_related=("investigator", "approved_by", "validation_protocol", "linked_parameter_log"),
    )
    context = {
        "capability_study": capability_study,
        "is_detail": True,
    }
    return render(request, "quality/processvalidation/process_capability_study/detail.html", context)


@login_required
def process_capability_study_create(request):
    if request.method == "POST":
        form = ProcessCapabilityStudyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Capability Study {obj.number} created and analyzed successfully.")
            return redirect("quality:process_capability_study_detail", pk=obj.pk)
    else:
        form = ProcessCapabilityStudyForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
        "capability_study": None,
    }
    return render(request, "quality/processvalidation/process_capability_study/form.html", context)


@login_required
def process_capability_study_edit(request, pk):
    capability_study = quality_object(request, ProcessCapabilityStudy, pk)
    if request.method == "POST":
        form = ProcessCapabilityStudyForm(request.POST, instance=capability_study, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Capability Study {obj.number} updated successfully.")
            return redirect("quality:process_capability_study_detail", pk=obj.pk)
    else:
        form = ProcessCapabilityStudyForm(instance=capability_study, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "capability_study": capability_study,
    }
    return render(request, "quality/processvalidation/process_capability_study/form.html", context)


@login_required
@require_POST
def process_capability_study_delete(request, pk):
    capability_study = quality_object(request, ProcessCapabilityStudy, pk)
    num = capability_study.number
    write_audit_log(request.user, capability_study, "delete", tenant=request.tenant)
    capability_study.delete()
    messages.success(request, f"Capability Study {num} deleted successfully.")
    return redirect("quality:process_capability_study_list")


@login_required
def process_capability_study_export(request):
    qs = quality_scope(ProcessCapabilityStudy.objects.all(), request).select_related(
        "investigator", "approved_by", "validation_protocol"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(parameter_name__icontains=q)
            | Q(process_name__icontains=q)
            | Q(equipment_tag__icontains=q)
            | Q(lot_number__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    determination_filter = request.GET.get("determination", "").strip()
    if determination_filter:
        qs = qs.filter(capability_determination=determination_filter)

    category_filter = request.GET.get("category", "").strip()
    if category_filter:
        qs = qs.filter(parameter_category=category_filter)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="capability_studies.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Number",
        "Title",
        "Parameter",
        "Category",
        "UOM",
        "USL",
        "LSL",
        "Target",
        "Mean",
        "Within StDev",
        "Overall StDev",
        "Cp",
        "Cpk",
        "Pp",
        "Ppk",
        "PPM",
        "Determination",
        "Status",
        "Investigator",
    ])

    for s in qs:
        writer.writerow([
            _csv_safe(s.number),
            _csv_safe(s.title),
            _csv_safe(s.parameter_name),
            _csv_safe(s.get_parameter_category_display()),
            _csv_safe(s.unit_of_measure),
            s.upper_spec_limit,
            s.lower_spec_limit,
            s.target_nominal or "",
            s.mean_value,
            s.within_subgroup_stdev or "",
            s.overall_stdev,
            s.cp_index or "",
            s.cpk_index or "",
            s.pp_index or "",
            s.ppk_index or "",
            s.expected_ppm or "",
            _csv_safe(s.get_capability_determination_display()),
            _csv_safe(s.get_status_display()),
            _csv_safe(s.investigator.get_full_name() if s.investigator else ""),
        ])

    return response
