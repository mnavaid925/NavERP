"""SCM 4.4 Warehouse Management — PickTask views (pick then pack)."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant, _post_pick
from apps.scm.models import Location, PickTask, StockMove
from apps.scm.forms import PickTaskForm, PickTaskLineFormSet, PickTaskPackForm


@login_required
def picktask_list(request):
    qs = (PickTask.objects.filter(tenant=request.tenant)
          .select_related("zone", "assigned_to")
          .annotate(line_total=Count("lines", distinct=True))
          # Count adds a GROUP BY that drops Meta ordering — re-assert it for stable pagination.
          .order_by("-created_at", "-id"))
    return crud_list(
        request, qs, "scm/warehouse/picktask/list.html",
        search_fields=["number", "wave_ref", "ship_to"],
        filters=[("status", "status", False), ("strategy", "strategy", False),
                 ("zone", "zone_id", True)],
        extra_context={
            "status_choices": PickTask.STATUS_CHOICES,
            "strategy_choices": PickTask.STRATEGY_CHOICES,
            "zones": Location.objects.filter(tenant=request.tenant),
        },
    )


@login_required
def picktask_create(request):
    return _picktask_form(request, instance=None)


@login_required
def picktask_edit(request, pk):
    obj = get_object_or_404(PickTask, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a pending or released pick can be edited.")
        return redirect("scm:picktask_detail", pk=pk)
    return _picktask_form(request, instance=obj)


def _picktask_form(request, instance):
    if instance is None and _need_tenant(request):
        return redirect("scm:picktask_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = PickTaskForm(request.POST, instance=instance, tenant=request.tenant)
        formset = PickTaskLineFormSet(request.POST, instance=instance,
                                      form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                task = form.save(commit=False)
                task.tenant = request.tenant
                task.save()
                formset.instance = task
                formset.save()
            write_audit_log(request.user, task, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"Pick task {task.number} saved.")
            return redirect("scm:picktask_detail", pk=task.pk)
    else:
        form = PickTaskForm(instance=instance, tenant=request.tenant)
        formset = PickTaskLineFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "scm/warehouse/picktask/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def picktask_detail(request, pk):
    obj = get_object_or_404(PickTask.objects.select_related("zone", "assigned_to"),
                            pk=pk, tenant=request.tenant)
    lines = list(obj.lines.select_related("item", "lot_serial", "from_location"))
    # Live availability per bin, resolved in ONE grouped query keyed by (item, lot) so a lot-tracked
    # line shows THAT lot at THAT bin — an item-level figure would overstate what's pickable.
    rows = (StockMove.objects
            .filter(tenant=request.tenant, item_id__in=[l.item_id for l in lines])
            .values("item_id", "location_id", "lot_serial_id").annotate(q=Sum("quantity")))
    qty_map = {(r["item_id"], r["location_id"], r["lot_serial_id"]): (r["q"] or Decimal("0"))
               for r in rows}
    line_rows = []
    for line in lines:
        if line.lot_serial_id:
            avail = qty_map.get((line.item_id, line.from_location_id, line.lot_serial_id), Decimal("0"))
        else:
            avail = sum((v for (i, loc, _), v in qty_map.items()
                         if i == line.item_id and loc == line.from_location_id), Decimal("0"))
        line_rows.append({"line": line, "available": avail})
    return render(request, "scm/warehouse/picktask/detail.html", {
        "obj": obj,
        "line_rows": line_rows,
        "pack_form": PickTaskPackForm(),
        "moves": (StockMove.objects.filter(tenant=request.tenant, reference=obj.number)
                  .select_related("item", "location") if obj.number else []),
    })


@login_required
@require_POST
def picktask_delete(request, pk):
    obj = get_object_or_404(PickTask, pk=pk, tenant=request.tenant)
    if obj.status not in ("pending", "cancelled"):
        messages.error(request, "Only a pending or cancelled pick can be deleted.")
        return redirect("scm:picktask_detail", pk=pk)
    return crud_delete(request, model=PickTask, pk=pk, success_url="scm:picktask_list")


@login_required
@require_POST
def picktask_release(request, pk):
    """Pending -> released: the task is now on the floor to be picked."""
    obj = get_object_or_404(PickTask, pk=pk, tenant=request.tenant)
    if obj.status != "pending":
        messages.info(request, "This pick has already been released.")
        return redirect("scm:picktask_detail", pk=pk)
    if not obj.lines.exists():
        messages.error(request, "Add at least one line before releasing the pick.")
        return redirect("scm:picktask_detail", pk=pk)
    obj.status = "released"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "release"})
    messages.success(request, f"Pick task {obj.number} released.")
    return redirect("scm:picktask_detail", pk=pk)


@login_required
@require_POST
def picktask_start(request, pk):
    """Released -> picking: a picker has taken the task and is walking it.

    Plain @login_required, unlike confirm: this moves NO stock, it just marks who is on the job so
    a released queue shows what has actually been picked up. Added because 'picking' was otherwise
    a state nothing could reach — filtering the list by it always returned zero rows (code review) —
    and both sibling entities (putaway, cycle count) already have the equivalent start action.
    """
    obj = get_object_or_404(PickTask, pk=pk, tenant=request.tenant)
    if obj.status != "released":
        messages.info(request, "Only a released pick can be started.")
        return redirect("scm:picktask_detail", pk=pk)
    obj.status = "picking"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "start"})
    messages.success(request, f"Pick {obj.number} started.")
    return redirect("scm:picktask_detail", pk=pk)


@tenant_admin_required
@require_POST
def picktask_confirm(request, pk):
    """Issue the picked quantities out of their bins and mark the task picked.

    Tenant-admin gated: this MOVES STOCK. Only what was actually picked leaves — a short pick issues
    the smaller quantity and stays visibly short on the detail page.
    """
    try:
        with transaction.atomic():
            obj = get_object_or_404(PickTask.objects.select_for_update(), pk=pk, tenant=request.tenant)
            if obj.status not in PickTask.PICKABLE_STATUSES:
                messages.info(request, "This pick is not in a state that can be confirmed.")
                return redirect("scm:picktask_detail", pk=pk)
            posted = _post_pick(obj, request.user)
            obj.status = "picked"
            obj.picked_at = timezone.now()
            obj.save(update_fields=["status", "picked_at", "updated_at"])
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:picktask_detail", pk=pk)
    write_audit_log(request.user, obj, "update", {"action": "confirm_pick", "lines": posted})
    messages.success(request, f"Pick {obj.number} confirmed — {posted} line(s) issued.")
    if obj.is_short():
        messages.warning(request, "Some lines were short-picked — check the line detail.")
    return redirect("scm:picktask_detail", pk=pk)


@login_required
@require_POST
def picktask_pack(request, pk):
    """Record packing details on a picked task. No stock effect — the goods already left the bins."""
    obj = get_object_or_404(PickTask, pk=pk, tenant=request.tenant)
    if obj.status != "picked":
        messages.error(request, "Only a picked task can be packed.")
        return redirect("scm:picktask_detail", pk=pk)
    form = PickTaskPackForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Check the packing details — the count and weight must be numbers.")
        return redirect("scm:picktask_detail", pk=pk)
    obj.package_count = form.cleaned_data.get("package_count")
    obj.package_weight = form.cleaned_data.get("package_weight")
    obj.tracking_ref = form.cleaned_data.get("tracking_ref") or ""
    obj.status = "packed"
    obj.packed_at = timezone.now()
    obj.save(update_fields=["package_count", "package_weight", "tracking_ref",
                            "status", "packed_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "pack"})
    messages.success(request, f"Pick {obj.number} packed and ready to ship.")
    return redirect("scm:picktask_detail", pk=pk)


@login_required
@require_POST
def picktask_cancel(request, pk):
    obj = get_object_or_404(PickTask, pk=pk, tenant=request.tenant)
    if obj.status in ("picked", "packed", "cancelled"):
        messages.info(request, "A picked or packed task can't be cancelled — its stock has already moved.")
        return redirect("scm:picktask_detail", pk=pk)
    obj.status = "cancelled"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "cancel"})
    messages.success(request, f"Pick task {obj.number} cancelled.")
    return redirect("scm:picktask_detail", pk=pk)
