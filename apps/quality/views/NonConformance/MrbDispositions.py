from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.quality.forms.NonConformance.MrbDispositions import MrbDispositionForm
from apps.quality.models.NonConformance.MrbDispositions import MrbDisposition
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport
from apps.quality.views._common import quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def mrb_disposition_list(request):
    qs = quality_scope(
        MrbDisposition.objects.select_related("ncr", "mrb_chair", "rework_assignee", "quality_approved_by"),
        request,
        owner_field="mrb_chair",
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(technical_justification__icontains=q)
            | Q(ncr__number__icontains=q)
            | Q(ncr__title__icontains=q)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_decision = request.GET.get("decision", "").strip()
    if selected_decision:
        qs = qs.filter(disposition_decision=selected_decision)

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)
    total_count = paginator.count

    context = {
        "mrb_dispositions": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "selected_status": selected_status,
        "selected_decision": selected_decision,
        "status_choices": MrbDisposition.STATUS_CHOICES,
        "decision_choices": MrbDisposition.DISPOSITION_DECISION_CHOICES,
        "total_count": total_count,
    }
    return render(request, "quality/nonconformance/mrbdisposition/list.html", context)


@login_required
def mrb_disposition_detail(request, pk):
    obj = quality_object(
        request,
        MrbDisposition,
        pk=pk,
        select_related=(
            "ncr",
            "mrb_chair",
            "rework_assignee",
            "reinspection_by",
            "quality_approved_by",
            "engineering_approved_by",
            "operations_approved_by",
        ),
    )
    return render(
        request,
        "quality/nonconformance/mrbdisposition/detail.html",
        {"mrb_disposition": obj},
    )


@login_required
def mrb_disposition_create(request):
    initial = {"mrb_chair": request.user}
    ncr_id = request.GET.get("ncr")
    if ncr_id and ncr_id.isdigit():
        ncr = NonConformanceReport.objects.filter(tenant=request.tenant, pk=int(ncr_id)).first()
        if ncr:
            initial["ncr"] = ncr
            initial["title"] = f"MRB Disposition for {ncr.number}: {ncr.title[:100]}"
            initial["technical_justification"] = f"Evaluation of defect {ncr.defect_code or ''} on item {ncr.affected_item_code or ''} ({ncr.quantity_nonconforming} {ncr.unit_of_measure})."

    if request.method == "POST":
        form = MrbDispositionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"MRB Disposition {obj.number} created successfully.")
            return redirect("quality:mrb_disposition_detail", pk=obj.pk)
    else:
        form = MrbDispositionForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "quality/nonconformance/mrbdisposition/form.html",
        {"form": form, "mrb_disposition": None, "is_edit": False},
    )


@login_required
def mrb_disposition_edit(request, pk):
    obj = quality_object(request, MrbDisposition, pk=pk)

    if request.method == "POST":
        form = MrbDispositionForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"MRB Disposition {obj.number} updated successfully.")
            return redirect("quality:mrb_disposition_detail", pk=obj.pk)
    else:
        form = MrbDispositionForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "quality/nonconformance/mrbdisposition/form.html",
        {"form": form, "mrb_disposition": obj, "is_edit": True},
    )


@login_required
@require_POST
def mrb_disposition_delete(request, pk):
    obj = quality_object(request, MrbDisposition, pk=pk)
    number = obj.number
    ncr_pk = obj.ncr_id
    next_url = request.POST.get("next") or request.GET.get("next")
    if obj.status in ("approved", "executed"):
        messages.error(request, f"Cannot delete approved or executed MRB Disposition {obj.number}.")
        if next_url:
            return redirect(next_url)
        if ncr_pk:
            return redirect("quality:non_conformance_report_detail", pk=ncr_pk)
        return redirect("quality:mrb_disposition_list")
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"MRB Disposition {number} deleted successfully.")
    if next_url:
        return redirect(next_url)
    if ncr_pk:
        return redirect("quality:non_conformance_report_detail", pk=ncr_pk)
    return redirect("quality:mrb_disposition_list")
