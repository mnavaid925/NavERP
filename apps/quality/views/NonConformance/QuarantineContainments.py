from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.quality.forms.NonConformance.QuarantineContainments import QuarantineContainmentForm
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport
from apps.quality.models.NonConformance.QuarantineContainments import QuarantineContainment
from apps.quality.views._common import quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def quarantine_containment_list(request):
    qs = quality_scope(
        QuarantineContainment.objects.select_related("ncr", "hold_applied_by", "released_by"),
        request,
        owner_field="hold_applied_by",
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(red_tag_number__icontains=q)
            | Q(quarantine_location__icontains=q)
            | Q(ncr__number__icontains=q)
            | Q(ncr__title__icontains=q)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_hold_type = request.GET.get("hold_type", "").strip()
    if selected_hold_type:
        qs = qs.filter(hold_type=selected_hold_type)

    total_count = qs.count()
    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "quarantine_containments": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "selected_status": selected_status,
        "selected_hold_type": selected_hold_type,
        "status_choices": QuarantineContainment.STATUS_CHOICES,
        "hold_type_choices": QuarantineContainment.HOLD_TYPE_CHOICES,
        "total_count": total_count,
    }
    return render(request, "quality/nonconformance/quarantinecontainment/list.html", context)


@login_required
def quarantine_containment_detail(request, pk):
    obj = quality_object(
        request,
        QuarantineContainment,
        pk=pk,
        select_related=("ncr", "hold_applied_by", "released_by"),
    )
    return render(
        request,
        "quality/nonconformance/quarantinecontainment/detail.html",
        {"quarantine_containment": obj},
    )


@login_required
def quarantine_containment_create(request):
    initial = {"hold_applied_by": request.user}
    ncr_id = request.GET.get("ncr")
    if ncr_id and ncr_id.isdigit():
        ncr = NonConformanceReport.objects.filter(tenant=request.tenant, pk=int(ncr_id)).first()
        if ncr:
            initial["ncr"] = ncr
            initial["quantity_on_hold"] = ncr.quantity_nonconforming
            initial["unit_of_measure"] = ncr.unit_of_measure
            initial["title"] = f"Quarantine Hold for {ncr.number}: {ncr.title[:100]}"

    if request.method == "POST":
        form = QuarantineContainmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "contain", tenant=request.tenant)
            messages.success(request, f"Quarantine Hold {obj.number} established successfully.")
            return redirect("quality:quarantine_containment_detail", pk=obj.pk)
    else:
        form = QuarantineContainmentForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "quality/nonconformance/quarantinecontainment/form.html",
        {"form": form, "quarantine_containment": None, "is_edit": False},
    )


@login_required
def quarantine_containment_edit(request, pk):
    obj = quality_object(request, QuarantineContainment, pk=pk)

    if request.method == "POST":
        form = QuarantineContainmentForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Quarantine Hold {obj.number} updated successfully.")
            return redirect("quality:quarantine_containment_detail", pk=obj.pk)
    else:
        form = QuarantineContainmentForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "quality/nonconformance/quarantinecontainment/form.html",
        {"form": form, "quarantine_containment": obj, "is_edit": True},
    )


@login_required
@require_POST
def quarantine_containment_delete(request, pk):
    obj = quality_object(request, QuarantineContainment, pk=pk)
    number = obj.number
    ncr_pk = obj.ncr_id
    next_url = request.POST.get("next") or request.GET.get("next")
    if obj.status == "active":
        messages.error(request, f"Cannot delete active Quarantine Hold {obj.number}. Release or scrap the inventory first.")
        if next_url:
            return redirect(next_url)
        if ncr_pk:
            return redirect("quality:non_conformance_report_detail", pk=ncr_pk)
        return redirect("quality:quarantine_containment_list")
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"Quarantine Hold {number} deleted successfully.")
    if next_url:
        return redirect(next_url)
    if ncr_pk:
        return redirect("quality:non_conformance_report_detail", pk=ncr_pk)
    return redirect("quality:quarantine_containment_list")
