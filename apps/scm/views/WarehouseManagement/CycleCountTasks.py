"""SCM 4.4 Warehouse Management — CycleCountTask views (schedule → count → reconcile)."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant, _post_adjustment
from apps.scm.models import (CycleCountTask, CycleCountTaskLine, Location, StockAdjustment,
                             StockAdjustmentLine, StockMove)
from apps.scm.forms import CycleCountTaskForm, CycleCountTaskLineFormSet


@login_required
def cyclecounttask_list(request):
    qs = (CycleCountTask.objects.filter(tenant=request.tenant)
          .select_related("location", "assigned_to", "adjustment"))
    return crud_list(
        request, qs, "scm/warehouse/cyclecounttask/list.html",
        search_fields=["number", "location__code", "notes"],
        filters=[("status", "status", False), ("count_method", "count_method", False),
                 ("location", "location_id", True)],
        extra_context={
            "status_choices": CycleCountTask.STATUS_CHOICES,
            "method_choices": CycleCountTask.METHOD_CHOICES,
            "locations": Location.objects.filter(tenant=request.tenant),
        },
    )


@login_required
def cyclecounttask_create(request):
    return _cyclecounttask_form(request, instance=None)


@login_required
def cyclecounttask_edit(request, pk):
    obj = get_object_or_404(CycleCountTask, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a scheduled or in-progress count can be edited.")
        return redirect("scm:cyclecounttask_detail", pk=pk)
    return _cyclecounttask_form(request, instance=obj)


def _cyclecounttask_form(request, instance):
    if instance is None and _need_tenant(request):
        return redirect("scm:cyclecounttask_list")
    is_edit = instance is not None
    # Past 'scheduled' the expected quantities have been snapshotted, so the sheet's composition is
    # frozen — the counter fills in counts, they don't redefine what is being counted. See
    # BaseCycleCountTaskLineFormSet for why an un-snapshotted row is a ledger-integrity hole.
    lock_sheet = is_edit and instance.status != "scheduled"
    if request.method == "POST":
        form = CycleCountTaskForm(request.POST, instance=instance, tenant=request.tenant)
        formset = CycleCountTaskLineFormSet(request.POST, instance=instance,
                                            form_kwargs={"tenant": request.tenant},
                                            lock_sheet=lock_sheet)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                task = form.save(commit=False)
                task.tenant = request.tenant
                task.save()
                formset.instance = task
                formset.save()
            write_audit_log(request.user, task, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"Cycle count {task.number} saved.")
            return redirect("scm:cyclecounttask_detail", pk=task.pk)
    else:
        form = CycleCountTaskForm(instance=instance, tenant=request.tenant)
        formset = CycleCountTaskLineFormSet(instance=instance, form_kwargs={"tenant": request.tenant},
                                            lock_sheet=lock_sheet)
    return render(request, "scm/warehouse/cyclecounttask/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance,
                   "lock_sheet": lock_sheet})


@login_required
def cyclecounttask_detail(request, pk):
    obj = get_object_or_404(
        CycleCountTask.objects.select_related("location", "assigned_to", "adjustment"),
        pk=pk, tenant=request.tenant)
    # Fetched ONCE and the totals derived from that same list. variance_count()/net_variance() each
    # open their own `self.lines.all()`, so calling them here would re-scan the sheet twice more —
    # three passes over one table for one page (perf review).
    lines = list(obj.lines.select_related("item", "lot_serial"))
    return render(request, "scm/warehouse/cyclecounttask/detail.html", {
        "obj": obj,
        "lines": lines,
        "variance_count": obj.variance_count(lines),
        "net_variance": obj.net_variance(lines),
    })


@login_required
@require_POST
def cyclecounttask_delete(request, pk):
    obj = get_object_or_404(CycleCountTask, pk=pk, tenant=request.tenant)
    if obj.status == "reconciled":
        messages.error(request, "A reconciled count can't be deleted — its adjustment stands.")
        return redirect("scm:cyclecounttask_detail", pk=pk)
    return crud_delete(request, model=CycleCountTask, pk=pk, success_url="scm:cyclecounttask_list")


@login_required
@require_POST
def cyclecounttask_start(request, pk):
    """Snapshot the expected quantities and open the count.

    The snapshot is taken HERE, server-side, from the derived on-hand — never typed by the counter
    and never re-derived at reconcile. Re-deriving later would quietly absorb any movement that
    happened during the count and hide the very discrepancy the count exists to find.
    """
    # Locked and re-checked inside the transaction, like every other posting action in 4.4: two
    # concurrent "Start" submits could otherwise both read 'scheduled' and both write a snapshot,
    # breaking the snapshotted-exactly-once invariant the whole feature rests on.
    with transaction.atomic():
        obj = get_object_or_404(
            CycleCountTask.objects.select_for_update().select_related("location"),
            pk=pk, tenant=request.tenant)
        if obj.status != "scheduled":
            messages.info(request, "This count has already been started.")
            return redirect("scm:cyclecounttask_detail", pk=pk)
        lines = list(obj.lines.select_related("item", "lot_serial"))
        if not lines:
            messages.error(request, "Add at least one item to count before starting.")
            return redirect("scm:cyclecounttask_detail", pk=pk)
        # One grouped query for every (item, lot) at this location rather than an aggregate per line.
        rows = (StockMove.objects
                .filter(tenant=request.tenant, location=obj.location,
                        item_id__in=[l.item_id for l in lines])
                .values("item_id", "lot_serial_id").annotate(q=Sum("quantity")))
        qty_map = {(r["item_id"], r["lot_serial_id"]): (r["q"] or Decimal("0")) for r in rows}
        for line in lines:
            if line.lot_serial_id:
                expected = qty_map.get((line.item_id, line.lot_serial_id), Decimal("0"))
            else:
                expected = sum((v for (i, _), v in qty_map.items() if i == line.item_id), Decimal("0"))
            line.expected_quantity = expected
        # One UPDATE for the whole sheet. A 'full' count covers a whole section, so a per-line
        # save() here would be O(lines) writes on exactly the document built to be large.
        CycleCountTaskLine.objects.bulk_update(lines, ["expected_quantity"])
        obj.status = "in_progress"
        obj.started_at = timezone.now()
        obj.save(update_fields=["status", "started_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "start", "lines": len(lines)})
    messages.success(request, f"Count {obj.number} started — expected quantities snapshotted.")
    return redirect("scm:cyclecounttask_detail", pk=pk)


@login_required
@require_POST
def cyclecounttask_complete(request, pk):
    """In progress -> counted. Requires every line to actually have been counted."""
    obj = get_object_or_404(CycleCountTask, pk=pk, tenant=request.tenant)
    if obj.status != "in_progress":
        messages.info(request, "Only a count in progress can be completed.")
        return redirect("scm:cyclecounttask_detail", pk=pk)
    uncounted = obj.lines.filter(counted_quantity__isnull=True).count()
    if uncounted:
        messages.error(request, f"{uncounted} line(s) still have no counted quantity.")
        return redirect("scm:cyclecounttask_detail", pk=pk)
    obj.status = "counted"
    obj.counted_at = timezone.now()
    obj.save(update_fields=["status", "counted_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "complete"})
    messages.success(request, f"Count {obj.number} completed — review the variances, then reconcile.")
    return redirect("scm:cyclecounttask_detail", pk=pk)


@tenant_admin_required
@require_POST
def cyclecounttask_reconcile(request, pk):
    """Turn the counted variances into stock reality.

    Generates exactly ONE `StockAdjustment(reason='cycle_count')` holding a line per variance, and
    posts it through the EXISTING adjustment path — there is deliberately no second way for a count
    to change stock. A count with no variance reconciles cleanly without creating an empty document.
    """
    try:
        with transaction.atomic():
            obj = get_object_or_404(
                CycleCountTask.objects.select_for_update().select_related("location"),
                pk=pk, tenant=request.tenant)
            if obj.status != "counted":
                messages.info(request, "Only a completed count can be reconciled.")
                return redirect("scm:cyclecounttask_detail", pk=pk)

            variances = [l for l in obj.lines.select_related("item", "lot_serial") if l.has_variance]
            adjustment = None
            if variances:
                adjustment = StockAdjustment.objects.create(
                    tenant=request.tenant, location=obj.location, reason="cycle_count",
                    status="draft", adjustment_date=timezone.localdate(),
                    notes=f"Generated from cycle count {obj.number}.")
                StockAdjustmentLine.objects.bulk_create([
                    StockAdjustmentLine(
                        adjustment=adjustment, item=line.item, lot_serial=line.lot_serial,
                        quantity_delta=line.variance,
                        unit_cost=line.item.average_cost or Decimal("0"))
                    for line in variances
                ])
                # Post through the SAME service every other adjustment uses.
                _post_adjustment(adjustment, request.user)
                adjustment.status = "posted"
                adjustment.posted_at = timezone.now()
                adjustment.save(update_fields=["status", "posted_at", "updated_at"])

            obj.adjustment = adjustment
            obj.status = "reconciled"
            obj.reconciled_at = timezone.now()
            obj.save(update_fields=["adjustment", "status", "reconciled_at", "updated_at"])
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:cyclecounttask_detail", pk=pk)
    write_audit_log(request.user, obj, "update",
                    {"action": "reconcile", "adjustment": adjustment.number if adjustment else None})
    if adjustment:
        messages.success(request, f"Count {obj.number} reconciled — adjustment {adjustment.number} posted.")
    else:
        messages.success(request, f"Count {obj.number} reconciled — no variances, stock was accurate.")
    return redirect("scm:cyclecounttask_detail", pk=pk)


@login_required
@require_POST
def cyclecounttask_cancel(request, pk):
    obj = get_object_or_404(CycleCountTask, pk=pk, tenant=request.tenant)
    if obj.status == "reconciled":
        messages.info(request, "A reconciled count can't be cancelled — correct it with a new adjustment.")
        return redirect("scm:cyclecounttask_detail", pk=pk)
    obj.status = "cancelled"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "cancel"})
    messages.success(request, f"Count {obj.number} cancelled.")
    return redirect("scm:cyclecounttask_detail", pk=pk)
