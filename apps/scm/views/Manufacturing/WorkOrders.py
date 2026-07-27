"""SCM 4.8 Manufacturing — WorkOrder views: the run lifecycle and the two stock postings.

Every action that moves stock is ``@tenant_admin_required @require_POST`` and does its work inside
``transaction.atomic()`` behind a ``select_for_update()`` row lock with the status re-read INSIDE
the transaction. Without that re-read two concurrent POSTs (a double-click, a retry, a replay) can
both see ``released`` and each post a full set of moves — silently doubling the stock consumed.
This is the shape 4.3's ``stocktransfer_complete`` established; do not simplify it away.
"""
from datetime import datetime, timedelta

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import (_insufficient_stock, _item_qs, _need_tenant,
                                     _post_stock_move, _shared_items)
# The clamped quantizer the models write every computed quantity through — a raw Decimal division
# here could exceed what DecimalField(14, 4) holds and fail the whole atomic block.
from apps.scm.models._base import q4
from apps.scm.models import BillOfMaterials, WorkCenter, WorkOrder, WorkOrderComponent
from apps.scm.forms import (WorkOrderComponentFormSet, WorkOrderForm, WorkOrderReportForm,
                            WorkOrderScheduleForm)

ZERO = Decimal("0")


@login_required
def workorder_list(request):
    qs = (WorkOrder.objects.filter(tenant=request.tenant)
          .select_related("item", "work_center", "bom", "sales_order", "output_location"))
    return crud_list(
        request, qs, "scm/manufacturing/workorder/list.html",
        search_fields=["number", "notes", "item__sku", "item__name", "bom__number",
                       "sales_order__number"],
        filters=[("status", "status", False), ("priority", "priority", False),
                 ("order_policy", "order_policy", False), ("item", "item_id", True),
                 ("work_center", "work_center_id", True)],
        extra_context={
            "status_choices": WorkOrder.STATUS_CHOICES,
            "priority_choices": WorkOrder.PRIORITY_CHOICES,
            "policy_choices": WorkOrder.ORDER_POLICY_CHOICES,
            "items": _item_qs(request.tenant),
            "work_centers": WorkCenter.objects.filter(tenant=request.tenant, is_active=True),
        },
    )


@login_required
def workorder_create(request):
    return _workorder_form(request, instance=None)


@login_required
def workorder_edit(request, pk):
    obj = get_object_or_404(WorkOrder, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, f"Work order {obj.number} is {obj.get_status_display().lower()} "
                                "and can no longer be edited.")
        return redirect("scm:workorder_detail", pk=pk)
    return _workorder_form(request, instance=obj)


def _workorder_form(request, instance):
    """Header + component formset in ONE transaction (the _load_form pattern).

    A brand-new run with a BOM and no hand-entered components is exploded on save, so the planner
    gets the material list without a second click. ``explode_components()`` is a no-op once any
    component row exists, so this can never overwrite a hand-edited set.
    """
    if instance is None and _need_tenant(request):
        return redirect("scm:workorder_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = WorkOrderForm(request.POST, instance=instance, tenant=request.tenant)
        formset = WorkOrderComponentFormSet(request.POST, instance=instance,
                                            form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                order = form.save(commit=False)
                order.tenant = request.tenant
                order.save()
                formset.instance = order
                formset.save()
                exploded = order.explode_components()
            write_audit_log(request.user, order, "update" if is_edit else "create", _changed(form))
            if exploded:
                messages.success(request, f"Work order {order.number} saved — {exploded} "
                                          "component(s) exploded from the BOM.")
            else:
                messages.success(request, f"Work order {order.number} saved.")
            return redirect("scm:workorder_detail", pk=order.pk)
    else:
        form = WorkOrderForm(instance=instance, tenant=request.tenant)
        formset = WorkOrderComponentFormSet(instance=instance,
                                            form_kwargs={"tenant": request.tenant})
    return render(request, "scm/manufacturing/workorder/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def workorder_detail(request, pk):
    obj = get_object_or_404(
        WorkOrder.objects.select_related("item", "uom", "bom", "work_center", "sales_order",
                                         "component_location", "output_location",
                                         "output_lot_serial", "released_by"),
        pk=pk, tenant=request.tenant)
    from apps.scm.models import StockMove
    components = obj.components.select_related("item", "uom", "lot_serial").all()
    labor_cost, machine_cost = obj._time_costs()
    return render(request, "scm/manufacturing/workorder/detail.html", {
        "obj": obj,
        "components": components,
        "shortfalls": obj.material_shortfalls(),
        "time_logs": obj.time_logs.select_related("work_center", "operator")[:20],
        # The ledger rows this run wrote — reference is the only link StockMove keeps to its source
        # document, exactly as the transfer and GRN detail pages do it.
        "moves": (StockMove.objects.filter(tenant=request.tenant, reference=obj.number)
                  .select_related("item", "location")[:50]),
        "material_cost": obj.material_cost,
        "labor_cost": labor_cost,
        "machine_cost": machine_cost,
        "wip_value": obj.wip_value,
        "schedule_form": WorkOrderScheduleForm(initial={
            "direction": obj.schedule_direction,
            "lead_time_days": obj.bom.lead_time_days if obj.bom_id else 0,
        }),
        "report_form": WorkOrderReportForm(),
    })


@login_required
@require_POST
def workorder_delete(request, pk):
    obj = get_object_or_404(WorkOrder, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a draft or planned work order can be deleted — cancel it "
                                "instead so its history survives.")
        return redirect("scm:workorder_detail", pk=pk)
    return crud_delete(request, model=WorkOrder, pk=pk, success_url="scm:workorder_list")


# ============================================================= lifecycle (no stock effect)
def _transition(request, pk, *, from_statuses, to_status, verb, stamp=None):
    """Shared status move — guard, stamp, audit, redirect. No stock moves here."""
    obj = get_object_or_404(WorkOrder, pk=pk, tenant=request.tenant)
    if obj.status not in from_statuses:
        messages.error(request, f"This work order can't be {verb} from "
                                f"{obj.get_status_display().lower()}.")
        return redirect("scm:workorder_detail", pk=pk)
    fields = ["status", "updated_at"]
    obj.status = to_status
    for field, value in (stamp or {}).items():
        setattr(obj, field, value)
        fields.append(field)
    obj.save(update_fields=fields)
    write_audit_log(request.user, obj, "update", {"action": verb, "status": to_status})
    messages.success(request, f"Work order {obj.number} {verb}.")
    return redirect("scm:workorder_detail", pk=pk)


@login_required
@require_POST
def workorder_plan(request, pk):
    return _transition(request, pk, from_statuses=("draft",), to_status="planned", verb="planned")


@tenant_admin_required
@require_POST
def workorder_release(request, pk):
    """Release the run to the shop floor.

    Tenant-admin gated even though it posts nothing itself: releasing is what unlocks the component
    issue and production posting, and it freezes the header against further editing.
    """
    obj = get_object_or_404(WorkOrder, pk=pk, tenant=request.tenant)
    if obj.status not in ("draft", "planned"):
        messages.error(request, "Only a draft or planned work order can be released.")
        return redirect("scm:workorder_detail", pk=pk)
    if not obj.components.exists():
        messages.error(request, "Add or explode at least one component before releasing.")
        return redirect("scm:workorder_detail", pk=pk)
    if obj.component_location_id is None or obj.output_location_id is None:
        messages.error(request, "Set both the component source and the output location before "
                                "releasing — the postings need somewhere to move stock from and to.")
        return redirect("scm:workorder_detail", pk=pk)
    return _transition(request, pk, from_statuses=("draft", "planned"), to_status="released",
                       verb="released", stamp={"released_by": request.user})


@tenant_admin_required
@require_POST
def workorder_close(request, pk):
    return _transition(request, pk, from_statuses=("completed",), to_status="closed",
                       verb="closed")


@tenant_admin_required
@require_POST
def workorder_cancel(request, pk):
    """Cancel a run that has not consumed anything.

    A run with consumption posted against it is NOT cancellable: the components are gone from stock
    and cancelling would leave that cost attached to a document claiming nothing happened. Close it
    instead, or post a compensating adjustment first — the same reasoning that makes StockMove
    append-only.
    """
    from apps.scm.models import StockMove
    obj = get_object_or_404(WorkOrder, pk=pk, tenant=request.tenant)
    if obj.status in ("closed", "cancelled"):
        messages.info(request, "This work order is already closed or cancelled.")
        return redirect("scm:workorder_detail", pk=pk)
    if StockMove.objects.filter(tenant=request.tenant, reference=obj.number).exists():
        messages.error(request, "This work order has posted stock movements and cannot be "
                                "cancelled — complete and close it, or reverse the movements first.")
        return redirect("scm:workorder_detail", pk=pk)
    return _transition(request, pk, from_statuses=("draft", "planned", "released", "in_progress"),
                       to_status="cancelled", verb="cancelled")


@login_required
@require_POST
def workorder_schedule(request, pk):
    """Fill the planned window by date arithmetic — see WorkOrderScheduleForm."""
    obj = get_object_or_404(WorkOrder, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a draft or planned work order can be rescheduled.")
        return redirect("scm:workorder_detail", pk=pk)
    form = WorkOrderScheduleForm(request.POST)
    if not form.is_valid():
        messages.error(request, "; ".join(
            f"{field}: {' '.join(errors)}" for field, errors in form.errors.items()))
        return redirect("scm:workorder_detail", pk=pk)
    direction = form.cleaned_data["direction"]
    anchor = form.cleaned_data["anchor_date"]
    days = form.cleaned_data.get("lead_time_days")
    if days is None:
        days = obj.bom.lead_time_days if obj.bom_id else 0
    anchor_dt = timezone.make_aware(
        datetime.combine(anchor, datetime.min.time()), timezone.get_current_timezone())
    if direction == "backward":
        obj.planned_end = anchor_dt
        obj.planned_start = anchor_dt - timedelta(days=days)
    else:
        obj.planned_start = anchor_dt
        obj.planned_end = anchor_dt + timedelta(days=days)
    obj.schedule_direction = direction
    obj.save(update_fields=["planned_start", "planned_end", "schedule_direction", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    {"action": "schedule", "direction": direction, "lead_time_days": days})
    messages.success(request, f"Work order {obj.number} scheduled "
                              f"{obj.planned_start:%d %b} → {obj.planned_end:%d %b}.")
    return redirect("scm:workorder_detail", pk=pk)


# ============================================================= postings (these move stock)
def _issue_components(order, components, quantities, user, moved_at=None):
    """Post one ``consumption`` StockMove per component. Assumes an enclosing atomic block.

    ``consumption``, NOT ``issue`` — see the model docstring: 4.7 reads ``issue`` as customer demand.
    ``_shared_items`` gives every line ONE Item instance so two lines for the same component roll the
    weighted-average cost cumulatively instead of the second overwriting the first.
    """
    moved_at = moved_at or timezone.now()
    items = _shared_items(components)
    posted = 0
    for component in components:
        quantity = quantities.get(component.pk, ZERO)
        if quantity <= ZERO:
            continue
        item = items[component.item_id]
        shortfall = _insufficient_stock(item, order.component_location, quantity,
                                        component.lot_serial)
        if shortfall:
            raise ValidationError(shortfall)
        cost = item.average_cost or item.standard_cost or ZERO
        _post_stock_move(order.tenant, item=item, location=order.component_location,
                         quantity=-quantity, move_type="consumption", unit_cost=cost,
                         lot_serial=component.lot_serial, reference=order.number,
                         reason=f"Consumed by {order.number}", moved_at=moved_at)
        # Roll the snapshot cost as a weighted average across partial issues. Overwriting it would
        # re-value the earlier issue at today's rate, so `issued_value` would disagree with the
        # ledger rows it is meant to summarise.
        already = component.quantity_issued or ZERO
        total = already + quantity
        component.unit_cost = q4(
            ((already * (component.unit_cost or ZERO)) + (quantity * cost)) / total)
        component.quantity_issued = q4(total)
        component.save(update_fields=["quantity_issued", "unit_cost"])
        posted += 1
    return posted


@tenant_admin_required
@require_POST
def workorder_issue_components(request, pk):
    """Draw the outstanding material for the run out of the component location."""
    try:
        with transaction.atomic():
            obj = get_object_or_404(
                WorkOrder.objects.select_for_update().select_related("component_location"),
                pk=pk, tenant=request.tenant)
            if obj.status not in WorkOrder.OPEN_STATUSES:
                messages.error(request, "Release the work order before issuing components.")
                return redirect("scm:workorder_detail", pk=pk)
            if obj.component_location_id is None:
                messages.error(request, "This work order has no component source location.")
                return redirect("scm:workorder_detail", pk=pk)
            # Manual lines only. A backflush line is consumed automatically in proportion to
            # reported output, so issuing it here would pre-consume it and make the issue-method
            # distinction inert — the planner would have no way to keep a line on backflush.
            components = [c for c in obj.components.select_related("item", "lot_serial").all()
                          if c.issue_method != "backflush"]
            quantities = {c.pk: c.quantity_outstanding for c in components}
            posted = _issue_components(obj, components, quantities, request.user)
            if not posted:
                messages.info(request, "Every manually-issued component is already fully issued "
                                       "(backflush lines are consumed when output is reported).")
                return redirect("scm:workorder_detail", pk=pk)
            if obj.status == "released":
                obj.status = "in_progress"
                obj.actual_start = obj.actual_start or timezone.now()
                obj.save(update_fields=["status", "actual_start", "updated_at"])
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:workorder_detail", pk=pk)
    write_audit_log(request.user, obj, "update", {"action": "issue_components", "lines": posted})
    messages.success(request, f"Issued {posted} component line(s) to {obj.number}.")
    return redirect("scm:workorder_detail", pk=pk)


@tenant_admin_required
@require_POST
def workorder_report_production(request, pk):
    """Report finished output — the ONLY writer of quantity_produced/scrapped/produced_unit_cost.

    Posts a ``production`` StockMove for the good quantity at the cost the run has actually absorbed
    so far. Scrap is recorded on the order but posts NO move: scrapped units never entered stock, so
    there is nothing to take out. Backflush components are consumed here in proportion to the output.
    """
    form = WorkOrderReportForm(request.POST)
    if not form.is_valid():
        messages.error(request, "; ".join(
            " ".join(errors) for errors in form.errors.values()))
        return redirect("scm:workorder_detail", pk=pk)
    good = form.cleaned_data.get("quantity_good") or ZERO
    scrapped = form.cleaned_data.get("quantity_scrapped") or ZERO
    backflush = form.cleaned_data.get("backflush")
    try:
        with transaction.atomic():
            obj = get_object_or_404(
                WorkOrder.objects.select_for_update().select_related(
                    "item", "output_location", "output_lot_serial", "component_location"),
                pk=pk, tenant=request.tenant)
            if obj.status not in WorkOrder.OPEN_STATUSES:
                messages.error(request, "Release the work order before reporting production.")
                return redirect("scm:workorder_detail", pk=pk)
            if obj.output_location_id is None:
                messages.error(request, "This work order has no output location.")
                return redirect("scm:workorder_detail", pk=pk)
            if good + scrapped > obj.quantity_remaining:
                messages.error(
                    request, f"That reports {good + scrapped} against only "
                             f"{obj.quantity_remaining} remaining on {obj.number}.")
                return redirect("scm:workorder_detail", pk=pk)

            if backflush:
                components = [c for c in obj.components.select_related("item", "lot_serial").all()
                              if c.issue_method == "backflush"]
                planned = obj.quantity_planned or Decimal("1")
                quantities = {
                    c.pk: min(q4((c.quantity_required or ZERO) * (good + scrapped) / planned),
                              c.quantity_outstanding)
                    for c in components
                }
                _issue_components(obj, components, quantities, request.user)

            cumulative_good = q4((obj.quantity_produced or ZERO) + good)
            # THIS layer's quantity, not the cumulative one — computed_unit_cost divides the
            # unabsorbed pool, so passing the cumulative figure would re-charge cost an earlier
            # layer already carried and over-value the move.
            unit_cost = obj.computed_unit_cost(good)
            if good > ZERO:
                _post_stock_move(obj.tenant, item=obj.item, location=obj.output_location,
                                 quantity=good, move_type="production", unit_cost=unit_cost,
                                 lot_serial=obj.output_lot_serial, reference=obj.number,
                                 reason=f"Produced by {obj.number}")
            obj.quantity_produced = cumulative_good
            obj.quantity_scrapped = q4((obj.quantity_scrapped or ZERO) + scrapped)
            obj.produced_unit_cost = unit_cost
            obj.actual_start = obj.actual_start or timezone.now()
            fields = ["quantity_produced", "quantity_scrapped", "produced_unit_cost",
                      "actual_start", "updated_at"]
            if obj.status == "released":
                obj.status = "in_progress"
                fields.append("status")
            if obj.quantity_remaining <= ZERO:
                obj.status = "completed"
                obj.actual_end = timezone.now()
                fields.extend(["status", "actual_end"])
            obj.save(update_fields=list(dict.fromkeys(fields)))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:workorder_detail", pk=pk)
    write_audit_log(request.user, obj, "update", {
        "action": "report_production", "good": str(good), "scrapped": str(scrapped),
        "unit_cost": str(obj.produced_unit_cost)})
    messages.success(request, f"Reported {good} good and {scrapped} scrapped on {obj.number} "
                              f"at {obj.produced_unit_cost} per unit.")
    return redirect("scm:workorder_detail", pk=pk)
