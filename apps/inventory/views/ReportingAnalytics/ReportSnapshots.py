"""Inventory 5.17 â€” InventoryReportSnapshot [IRS-] CRUD.

The freeze surface for the four live reports: GENERATE runs the same engine the
page runs and stores a scalar-only summary (module docstring on the model), LIST
and DETAIL read frozen rows back, DELETE is admin-gated because a snapshot is
audit evidence. There is deliberately NO edit route â€” a snapshot that could be
edited would not be evidence.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.crud import crud_delete, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.inventory.forms import ReportSnapshotForm
from apps.inventory.models import InventoryReportSnapshot
# Direct-submodule import: the ReportingAnalytics package __init__ imports THIS
# module, so constants routed through the package would be a circular import.
from apps.inventory.views.ReportingAnalytics import _engine


@login_required
def snapshot_list(request):
    qs = (InventoryReportSnapshot.objects.filter(tenant=request.tenant)
          .select_related("location", "generated_by"))
    report_type = request.GET.get("type", "").strip()
    if report_type:
        qs = qs.filter(report_type=report_type)
    q = request.GET.get("q", "").strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(Q(number__icontains=q) | Q(title__icontains=q))
    page_obj = paginate(request, qs, per_page=20)
    return render(request, "inventory/reports/snapshot/list.html", {
        "page_obj": page_obj,
        "object_list": page_obj.object_list,
        "type_choices": InventoryReportSnapshot.REPORT_TYPES,
        "report_type": report_type,
        "q": q,
    })


@login_required
def snapshot_generate(request):
    """GET renders the form; POST computes the chosen report LIVE and freezes it.

    The form is built with ``tenant=`` like every sibling custom-form view:
    without it TenantModelForm cannot scope the location queryset (foreign
    locations would render in the dropdown) and ``_reject_foreign`` would
    reject even this workspace's own locations. The ``?type=`` deep-link the
    four report pages send pre-selects the report type on GET.
    """
    initial = None
    if request.method == "GET":
        wanted = request.GET.get("type", "")
        if any(wanted == value for value, _label in InventoryReportSnapshot.REPORT_TYPES):
            initial = {"report_type": wanted}
    form = ReportSnapshotForm(request.POST or None, initial=initial, tenant=request.tenant)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.tenant = request.tenant
        obj.generated_by = request.user
        obj.summary = _engine.build_summary(
            obj.report_type, request.tenant,
            location=form.cleaned_data.get("location"),
            window_days=form.cleaned_data.get("window_days"))
        obj.save()
        write_audit_log(request.user, obj, "create", tenant=request.tenant)
        messages.success(request, f"Snapshot {obj.number} generated.")
        return redirect("inventory:snapshot_detail", pk=obj.pk)
    return render(request, "inventory/reports/snapshot/form.html", {
        "form": form,
        "object": None,
        "type_choices": InventoryReportSnapshot.REPORT_TYPES,
    })


@login_required
def snapshot_detail(request, pk):
    obj = get_object_or_404(InventoryReportSnapshot, pk=pk, tenant=request.tenant)
    return render(request, "inventory/reports/snapshot/detail.html", {"object": obj})


@tenant_admin_required
@require_POST
def snapshot_delete(request, pk):
    # crud_delete re-scopes by tenant itself; audit row is part of the helper.
    return crud_delete(request, model=InventoryReportSnapshot, pk=pk,
                       success_url="inventory:snapshot_list")
