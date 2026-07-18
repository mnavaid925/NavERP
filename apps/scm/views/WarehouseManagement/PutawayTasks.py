"""SCM 4.4 Warehouse Management — PutawayTask views."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant, _post_putaway
from apps.scm.models import Location, PutawayTask
from apps.scm.forms import PutawayTaskForm


@login_required
def putawaytask_list(request):
    qs = (PutawayTask.objects.filter(tenant=request.tenant)
          .select_related("item", "from_location", "to_location", "assigned_to"))
    return crud_list(
        request, qs, "scm/warehouse/putawaytask/list.html",
        search_fields=["number", "item__sku", "item__name", "to_location__code"],
        filters=[("status", "status", False), ("strategy", "strategy", False),
                 ("to_location", "to_location_id", True)],
        extra_context={
            "status_choices": PutawayTask.STATUS_CHOICES,
            "strategy_choices": PutawayTask.STRATEGY_CHOICES,
            "locations": Location.objects.filter(tenant=request.tenant),
        },
    )


@login_required
def putawaytask_create(request):
    if _need_tenant(request):
        return redirect("scm:putawaytask_list")
    return crud_create(request, form_class=PutawayTaskForm,
                       template="scm/warehouse/putawaytask/form.html",
                       success_url="scm:putawaytask_list")


@login_required
def putawaytask_edit(request, pk):
    obj = get_object_or_404(PutawayTask, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a pending or in-progress putaway can be edited.")
        return redirect("scm:putawaytask_detail", pk=pk)
    return crud_edit(request, model=PutawayTask, pk=pk, form_class=PutawayTaskForm,
                     template="scm/warehouse/putawaytask/form.html",
                     success_url="scm:putawaytask_list")


@login_required
def putawaytask_detail(request, pk):
    obj = get_object_or_404(
        PutawayTask.objects.select_related("item", "lot_serial", "from_location", "to_location",
                                           "goods_receipt", "assigned_to"),
        pk=pk, tenant=request.tenant)
    from apps.scm.models import StockMove
    return render(request, "scm/warehouse/putawaytask/detail.html", {
        "obj": obj,
        # What the source can actually cover right now, so the operator sees a shortfall up front.
        "available": obj.item.on_hand(location=obj.from_location),
        "moves": (StockMove.objects.filter(tenant=request.tenant, reference=obj.number)
                  .select_related("item", "location") if obj.number else []),
    })


@login_required
@require_POST
def putawaytask_delete(request, pk):
    obj = get_object_or_404(PutawayTask, pk=pk, tenant=request.tenant)
    if obj.status == "completed":
        messages.error(request, "A completed putaway can't be deleted — its stock movement stands.")
        return redirect("scm:putawaytask_detail", pk=pk)
    return crud_delete(request, model=PutawayTask, pk=pk, success_url="scm:putawaytask_list")


@login_required
@require_POST
def putawaytask_start(request, pk):
    """Pending -> in progress. Claims the task for whoever started it if nobody is assigned."""
    obj = get_object_or_404(PutawayTask, pk=pk, tenant=request.tenant)
    if obj.status != "pending":
        messages.info(request, "This putaway is already underway or closed.")
        return redirect("scm:putawaytask_detail", pk=pk)
    obj.status = "in_progress"
    if obj.assigned_to_id is None:
        obj.assigned_to = request.user
    obj.save(update_fields=["status", "assigned_to", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "start"})
    messages.success(request, f"Putaway {obj.number} started.")
    return redirect("scm:putawaytask_detail", pk=pk)


@tenant_admin_required
@require_POST
def putawaytask_complete(request, pk):
    """Post the staging→bin movement and close the task.

    Tenant-admin gated: this MOVES STOCK. The row is locked and its status re-read inside the
    transaction so two concurrent completions can't both post the pair.
    """
    try:
        with transaction.atomic():
            obj = get_object_or_404(
                PutawayTask.objects.select_for_update().select_related(
                    "item", "lot_serial", "from_location", "to_location"),
                pk=pk, tenant=request.tenant)
            if not obj.is_open:
                messages.info(request, "This putaway is already completed or cancelled.")
                return redirect("scm:putawaytask_detail", pk=pk)
            _post_putaway(obj, request.user)
            obj.status = "completed"
            obj.completed_at = timezone.now()
            obj.save(update_fields=["status", "completed_at", "updated_at"])
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:putawaytask_detail", pk=pk)
    write_audit_log(request.user, obj, "update", {"action": "complete"})
    messages.success(request, f"Putaway {obj.number} completed — stock moved to {obj.to_location.code}.")
    return redirect("scm:putawaytask_detail", pk=pk)


@login_required
@require_POST
def putawaytask_cancel(request, pk):
    obj = get_object_or_404(PutawayTask, pk=pk, tenant=request.tenant)
    if not obj.is_open:
        messages.info(request, "A completed putaway can't be cancelled — reverse it with a transfer.")
        return redirect("scm:putawaytask_detail", pk=pk)
    obj.status = "cancelled"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "cancel"})
    messages.success(request, f"Putaway {obj.number} cancelled.")
    return redirect("scm:putawaytask_detail", pk=pk)
