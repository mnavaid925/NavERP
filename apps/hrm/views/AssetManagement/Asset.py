"""HRM 3.33 Asset Management — Asset views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    Asset,
    AssetAllocation,
    EmployeeProfile,
)
from apps.hrm.forms import (
    AssetForm,
)


@login_required
def asset_list(request):
    return crud_list(
        request,
        Asset.objects.filter(tenant=request.tenant).select_related("location", "current_holder__party", "currency"),
        "hrm/assets/asset/list.html",
        search_fields=["number", "asset_tag", "name", "serial_number"],
        filters=[("status", "status", False), ("category", "category", False),
                 ("location", "location_id", True), ("current_holder", "current_holder_id", True)],
        extra_context={"status_choices": Asset.STATUS_CHOICES,
                       "category_choices": AssetAllocation.ASSET_CATEGORY_CHOICES,
                       "locations": OrgUnit.objects.filter(tenant=request.tenant, kind="department").order_by("name"),
                       "holders": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def asset_create(request):
    return crud_create(request, form_class=AssetForm, template="hrm/assets/asset/form.html",
                       success_url="hrm:asset_list")


@login_required
def asset_detail(request, pk):
    obj = get_object_or_404(
        Asset.objects.select_related("location", "current_holder__party", "currency"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/assets/asset/detail.html", {
        "obj": obj,
        "allocations": obj.allocations.select_related("employee__party", "issued_by").order_by("-issued_at"),
        "maintenance_records": obj.maintenance_records.order_by("-scheduled_date"),
        "assignable_employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                                 .select_related("party").order_by("party__name")),
    })


@login_required
def asset_edit(request, pk):
    return crud_edit(request, model=Asset, pk=pk, form_class=AssetForm,
                     template="hrm/assets/asset/form.html", success_url="hrm:asset_list")


@login_required
@require_POST
def asset_delete(request, pk):
    obj = get_object_or_404(Asset, pk=pk, tenant=request.tenant)
    if obj.status in ("assigned", "in_repair"):
        messages.error(request, "Return this asset or complete its repair before deleting it.")
        return redirect("hrm:asset_detail", pk=obj.pk)
    return crud_delete(request, model=Asset, pk=pk, success_url="hrm:asset_list")


@login_required
@require_POST
def asset_assign(request, pk):
    emp_pk = (request.POST.get("employee") or "").strip()
    return_due = parse_date((request.POST.get("return_due_date") or "").strip() or "")
    notes = (request.POST.get("notes") or "").strip()
    # Lock the asset row for the check-and-create so two concurrent assigns can't both pass the
    # in-stock check and double-issue one asset (TOCTOU).
    with transaction.atomic():
        obj = get_object_or_404(Asset.objects.select_for_update(), pk=pk, tenant=request.tenant)
        if obj.status != "in_stock":
            messages.error(request, "Only an in-stock asset can be assigned.")
            return redirect("hrm:asset_detail", pk=obj.pk)
        employee = (EmployeeProfile.objects.filter(tenant=request.tenant, pk=int(emp_pk)).first()
                    if emp_pk.isdecimal() else None)
        if employee is None:
            messages.error(request, "Select a valid employee to assign this asset to.")
            return redirect("hrm:asset_detail", pk=obj.pk)
        allocation = AssetAllocation.objects.create(
            tenant=request.tenant, employee=employee, asset=obj, asset_name=obj.name,
            asset_category=obj.category, serial_number=obj.serial_number, asset_tag=obj.asset_tag,
            status="issued", issued_at=timezone.now(), issued_by=request.user,
            return_due_date=return_due, notes=notes)  # .save() syncs obj.status/current_holder
    write_audit_log(request.user, obj, "update",
                    {"action": "assign", "employee": str(employee), "allocation": allocation.number})
    messages.success(request, f"Asset assigned to {employee}.")
    return redirect("hrm:asset_detail", pk=obj.pk)


@login_required
@require_POST
def asset_return(request, pk):
    obj = get_object_or_404(Asset, pk=pk, tenant=request.tenant)
    allocation = (obj.allocations.filter(tenant=request.tenant, status="issued")
                  .order_by("-issued_at").first())
    if allocation is None:
        messages.error(request, "This asset has no active allocation to return.")
        return redirect("hrm:asset_detail", pk=obj.pk)
    allocation.status = "returned"
    allocation.returned_at = timezone.now()
    allocation.save(update_fields=["status", "returned_at", "updated_at"])  # syncs obj back to in_stock
    write_audit_log(request.user, obj, "update", {"action": "return", "allocation": allocation.number})
    messages.success(request, "Asset returned to stock.")
    return redirect("hrm:asset_detail", pk=obj.pk)


@login_required
@require_POST
def asset_retire(request, pk):
    obj = get_object_or_404(Asset, pk=pk, tenant=request.tenant)
    if obj.status not in ("in_stock", "in_repair"):
        messages.error(request, "Return or repair-complete this asset before retiring it.")
        return redirect("hrm:asset_detail", pk=obj.pk)
    obj.status = "retired"
    obj.current_holder = None
    obj.save(update_fields=["status", "current_holder", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "retire"})
    messages.success(request, "Asset retired.")
    return redirect("hrm:asset_detail", pk=obj.pk)


@login_required
@require_POST
def asset_dispose(request, pk):
    obj = get_object_or_404(Asset, pk=pk, tenant=request.tenant)
    if obj.status != "retired":
        messages.error(request, "Only a retired asset can be disposed.")
        return redirect("hrm:asset_detail", pk=obj.pk)
    obj.status = "disposed"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "dispose"})
    messages.success(request, "Asset disposed.")
    return redirect("hrm:asset_detail", pk=obj.pk)
