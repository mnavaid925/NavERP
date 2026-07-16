"""HRM 3.33 Asset Management — Assetmaintenance views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    Asset,
    AssetMaintenance,
)
from apps.hrm.forms import (
    AssetMaintenanceForm,
)


@login_required
def assetmaintenance_list(request):
    return crud_list(
        request,
        AssetMaintenance.objects.filter(tenant=request.tenant).select_related("asset"),
        "hrm/assets/assetmaintenance/list.html",
        search_fields=["number", "vendor", "asset__name"],
        filters=[("status", "status", False), ("maintenance_type", "maintenance_type", False),
                 ("asset", "asset_id", True)],
        extra_context={"status_choices": AssetMaintenance.STATUS_CHOICES,
                       "type_choices": AssetMaintenance.TYPE_CHOICES,
                       "assets": Asset.objects.filter(tenant=request.tenant).order_by("name")},
    )


@login_required
def assetmaintenance_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    asset_pk = (request.GET.get("asset") or "").strip()
    if request.method == "POST":
        form = AssetMaintenanceForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()  # AssetMaintenance.save() runs _sync_asset_status() atomically (repair in/out of service)
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Maintenance record logged.")
            if asset_pk.isdecimal():
                return redirect("hrm:asset_detail", pk=obj.asset_id)
            return redirect("hrm:assetmaintenance_list")
    else:
        form = AssetMaintenanceForm(tenant=request.tenant,
                                    initial={"asset": asset_pk if asset_pk.isdecimal() else None})
    return render(request, "hrm/assets/assetmaintenance/form.html", {"form": form, "is_edit": False})


@login_required
def assetmaintenance_detail(request, pk):
    obj = get_object_or_404(AssetMaintenance.objects.select_related("asset"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/assets/assetmaintenance/detail.html", {"obj": obj})


@login_required
def assetmaintenance_edit(request, pk):
    return crud_edit(request, model=AssetMaintenance, pk=pk, form_class=AssetMaintenanceForm,
                     template="hrm/assets/assetmaintenance/form.html", success_url="hrm:assetmaintenance_list")


@login_required
@require_POST
def assetmaintenance_delete(request, pk):
    obj = get_object_or_404(AssetMaintenance.objects.select_related("asset"), pk=pk, tenant=request.tenant)
    # Deleting the active repair that put the asset "in_repair" would strand it there (delete()
    # doesn't run the save()-sync) — require completing/cancelling the repair first.
    if (obj.maintenance_type == "repair" and obj.status in ("scheduled", "in_progress")
            and obj.asset.status == "in_repair"):
        messages.error(request, "Complete or cancel this repair first — the asset is currently in repair.")
        return redirect("hrm:assetmaintenance_detail", pk=obj.pk)
    return crud_delete(request, model=AssetMaintenance, pk=pk, success_url="hrm:assetmaintenance_list")


@login_required
@require_POST
def assetmaintenance_complete(request, pk):
    obj = get_object_or_404(AssetMaintenance.objects.select_related("asset"), pk=pk, tenant=request.tenant)
    if obj.status in ("scheduled", "in_progress"):
        obj.status = "completed"
        obj.completed_date = obj.completed_date or timezone.localdate()
        obj.save(update_fields=["status", "completed_date", "updated_at"])  # save() returns a repaired asset to service
        write_audit_log(request.user, obj, "update", {"action": "complete"})
        messages.success(request, "Maintenance marked complete.")
    return redirect("hrm:assetmaintenance_detail", pk=obj.pk)
