from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.quality.forms.NonConformance.ProcessDeviations import ProcessDeviationForm
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport
from apps.quality.models.NonConformance.ProcessDeviations import ProcessDeviation
from apps.quality.views._common import quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def process_deviation_list(request):
    qs = quality_scope(
        ProcessDeviation.objects.select_related("ncr", "controlled_document", "department", "requested_by", "approved_by"),
        request,
        owner_field="requested_by",
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(quality_impact_assessment__icontains=q)
            | Q(affected_lots_summary__icontains=q)
            | Q(ncr__number__icontains=q)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_deviation_type = request.GET.get("deviation_type", "").strip()
    if selected_deviation_type:
        qs = qs.filter(deviation_type=selected_deviation_type)

    selected_risk_level = request.GET.get("risk_level", "").strip()
    if selected_risk_level:
        qs = qs.filter(risk_impact_level=selected_risk_level)

    total_count = qs.count()
    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "process_deviations": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "selected_status": selected_status,
        "selected_deviation_type": selected_deviation_type,
        "selected_risk_level": selected_risk_level,
        "status_choices": ProcessDeviation.STATUS_CHOICES,
        "deviation_type_choices": ProcessDeviation.DEVIATION_TYPE_CHOICES,
        "risk_level_choices": ProcessDeviation.RISK_IMPACT_CHOICES,
        "total_count": total_count,
    }
    return render(request, "quality/nonconformance/processdeviation/list.html", context)


@login_required
def process_deviation_detail(request, pk):
    obj = quality_object(
        request,
        ProcessDeviation,
        pk=pk,
        select_related=("ncr", "controlled_document", "department", "requested_by", "approved_by"),
    )
    return render(
        request,
        "quality/nonconformance/processdeviation/detail.html",
        {"process_deviation": obj},
    )


@login_required
def process_deviation_create(request):
    initial = {"requested_by": request.user}
    ncr_id = request.GET.get("ncr")
    if ncr_id and ncr_id.isdigit():
        ncr = NonConformanceReport.objects.filter(tenant=request.tenant, pk=int(ncr_id)).first()
        if ncr:
            initial["ncr"] = ncr
            initial["deviation_type"] = "unplanned"
            initial["title"] = f"Unplanned Deviation for {ncr.number}: {ncr.title[:100]}"
            initial["affected_lots_summary"] = ncr.lot_serial_numbers

    if request.method == "POST":
        form = ProcessDeviationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Process Deviation {obj.number} recorded successfully.")
            return redirect("quality:process_deviation_detail", pk=obj.pk)
    else:
        form = ProcessDeviationForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "quality/nonconformance/processdeviation/form.html",
        {"form": form, "process_deviation": None, "is_edit": False},
    )


@login_required
def process_deviation_edit(request, pk):
    obj = quality_object(request, ProcessDeviation, pk=pk)

    if request.method == "POST":
        form = ProcessDeviationForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Process Deviation {obj.number} updated successfully.")
            return redirect("quality:process_deviation_detail", pk=obj.pk)
    else:
        form = ProcessDeviationForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "quality/nonconformance/processdeviation/form.html",
        {"form": form, "process_deviation": obj, "is_edit": True},
    )


@login_required
@require_POST
def process_deviation_delete(request, pk):
    obj = quality_object(request, ProcessDeviation, pk=pk)
    number = obj.number
    ncr_pk = obj.ncr_id
    next_url = request.POST.get("next") or request.GET.get("next")
    if obj.status in ("approved", "active", "closed"):
        messages.error(request, f"Cannot delete process deviation {obj.number} with status '{obj.get_status_display()}'.")
        if next_url:
            return redirect(next_url)
        if ncr_pk:
            return redirect("quality:non_conformance_report_detail", pk=ncr_pk)
        return redirect("quality:process_deviation_list")
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"Process Deviation {number} deleted successfully.")
    if next_url:
        return redirect(next_url)
    if ncr_pk:
        return redirect("quality:non_conformance_report_detail", pk=ncr_pk)
    return redirect("quality:process_deviation_list")
