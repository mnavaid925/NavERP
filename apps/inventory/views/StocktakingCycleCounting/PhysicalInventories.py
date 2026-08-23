"""Inventory 5.11 Stocktaking & Cycle Counting — PhysicalInventory views.

CRUD plus the three lifecycle verbs (start / reconcile / cancel). The model owns the
locking and guards; these views own the HTTP contract: POST-only verbs whose refusals
are expected traffic and land as flash messages on the detail page.
"""
from django.core.exceptions import ValidationError

from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms import PhysicalInventoryForm
from apps.inventory.models import PhysicalInventory


def _scoped(tenant):
    return (PhysicalInventory.objects.filter(tenant=tenant)
            .select_related("warehouse", "requested_by"))


@login_required
def physicalinventory_list(request):
    qs = _scoped(request.tenant)
    return crud_list(
        request, qs, "inventory/stocktake/physicalinventory/list.html",
        search_fields=["number", "warehouse__code", "notes"],
        filters=[("status", "status", False), ("frozen", "is_frozen", False)],
        extra_context={
            "status_choices": PhysicalInventory.STATUS_CHOICES,
            "frozen_count": (PhysicalInventory.objects
                             .filter(tenant=request.tenant, is_frozen=True).count()),
        },
    )


@login_required
def physicalinventory_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    sheets = (obj.spawned_tasks().select_related("location")
              .order_by("status", "scheduled_date"))
    total = sheets.count()
    reconciled = sheets.filter(status="reconciled").count()
    return render(request, "inventory/stocktake/physicalinventory/detail.html", {
        "obj": obj,
        "sheets": sheets[:25],
        "sheet_total": total,
        "sheet_reconciled": reconciled,
    })


@login_required
def physicalinventory_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = PhysicalInventoryForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.requested_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Created successfully.")
            return redirect("inventory:physicalinventory_list")
    else:
        form = PhysicalInventoryForm(tenant=request.tenant)
    return render(request, "inventory/stocktake/physicalinventory/form.html",
                  {"form": form, "is_edit": False})


@login_required
def physicalinventory_edit(request, pk):
    obj = get_object_or_404(PhysicalInventory, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} "
                                "and cannot be edited.")
        return redirect("inventory:physicalinventory_detail", pk=obj.pk)
    return crud_edit(
        request, model=PhysicalInventory, pk=pk, form_class=PhysicalInventoryForm,
        template="inventory/stocktake/physicalinventory/form.html",
        success_url="inventory:physicalinventory_list",
    )


@login_required
@require_POST
def physicalinventory_delete(request, pk):
    obj = get_object_or_404(PhysicalInventory, pk=pk, tenant=request.tenant)
    if not obj.is_editable or obj.is_frozen:
        messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} "
                                "— only a draft event can be deleted; cancel it instead.")
        return redirect("inventory:physicalinventory_detail", pk=obj.pk)
    if obj.spawned_tasks().exists():
        messages.error(request, f"{obj.number} already spawned count sheets — cancel "
                                "it rather than deleting its provenance.")
        return redirect("inventory:physicalinventory_detail", pk=obj.pk)
    return crud_delete(request, model=PhysicalInventory, pk=pk,
                       success_url="inventory:physicalinventory_list")


@login_required
@require_POST
def physicalinventory_start(request, pk):
    return _run_action(request, pk, "start")


@login_required
@require_POST
def physicalinventory_reconcile(request, pk):
    return _run_action(request, pk, "reconcile")


@login_required
@require_POST
def physicalinventory_cancel(request, pk):
    return _run_action(request, pk, "cancel")


_ACTION_MESSAGES = {
    "start": "started — warehouse frozen and count sheets spawned.",
    "reconcile": "reconciled — freeze lifted.",
    "cancel": "cancelled.",
}


def _run_action(request, pk, action):
    obj = get_object_or_404(PhysicalInventory, pk=pk, tenant=request.tenant)
    try:
        getattr(obj, action)(request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, f"{obj.number} {_ACTION_MESSAGES[action]}.")
    return redirect("inventory:physicalinventory_detail", pk=obj.pk)
