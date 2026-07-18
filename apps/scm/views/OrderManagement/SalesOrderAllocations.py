"""SCM 4.5 Order Management System — SalesOrderAllocation views (reserve / release / cancel).

None of these post a StockMove. See the model docstring: an allocation is a soft claim, and stock
only physically moves through 4.4's PickTask.
"""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant
from apps.scm.models import Location, SalesOrderAllocation, SalesOrderLine
from apps.scm.forms import SalesOrderAllocationForm

ZERO = Decimal("0")


def _lock_item(item_id):
    """Take a row lock on the item so an availability check and the reservation that follows are
    one atomic decision. Must be called inside transaction.atomic()."""
    from apps.scm.models import Item
    if item_id is not None:
        list(Item.objects.select_for_update().filter(pk=item_id))


def _available_to_promise(item, location, exclude_pk=None):
    """What can still be promised of ``item`` at ``location``.

    On-hand MINUS everything already reserved there. On-hand alone would over-promise: it counts
    stock that is physically present but already spoken for by another order, so two customers would
    each be told they can have the same unit.

    On-hand-only ATP — incoming purchase orders are deliberately NOT counted as available. Promising
    against stock that has not arrived needs supplier lead-time confidence this module does not
    have; that is the "supply-aware ATP" tier left to a later pass.

    ``exclude_pk`` lets an EDIT ignore its own current reservation, so re-saving a row without
    changing its quantity doesn't count that quantity twice and reject itself.
    """
    if item is None or location is None:
        return ZERO
    on_hand = item.on_hand(location=location)
    reserved_qs = (SalesOrderAllocation.objects
                   .filter(sales_order_line__item=item, location=location)
                   .exclude(status="cancelled"))
    if exclude_pk is not None:
        reserved_qs = reserved_qs.exclude(pk=exclude_pk)
    reserved = reserved_qs.aggregate(s=Sum("quantity"))["s"] or ZERO
    available = on_hand - reserved
    return available if available > ZERO else ZERO


@login_required
def salesorderallocation_list(request):
    qs = (SalesOrderAllocation.objects.filter(tenant=request.tenant)
          .select_related("location", "sales_order_line__item",
                          "sales_order_line__sales_order__customer"))
    return crud_list(
        request, qs, "scm/orders/salesorderallocation/list.html",
        search_fields=["sales_order_line__sales_order__number", "sales_order_line__item__sku",
                       "sales_order_line__item__name", "notes"],
        filters=[("status", "status", False), ("location", "location_id", True)],
        extra_context={
            "status_choices": SalesOrderAllocation.STATUS_CHOICES,
            "locations": Location.objects.filter(tenant=request.tenant),
        },
    )


@login_required
def salesorderallocation_detail(request, pk):
    obj = get_object_or_404(
        SalesOrderAllocation.objects.select_related(
            "location", "sales_order_line__item", "sales_order_line__sales_order__customer"),
        pk=pk, tenant=request.tenant)
    return render(request, "scm/orders/salesorderallocation/detail.html", {
        "obj": obj,
        "order": obj.sales_order_line.sales_order,
        "line": obj.sales_order_line,
    })


@tenant_admin_required
def salesorderallocation_create(request, line_pk):
    """Reserve stock for one order line. Tenant-admin gated — it commits inventory to a customer.

    The line comes from the URL and is scoped through its parent order's tenant (the line table has
    no tenant column of its own), so a crafted line_pk from another workspace 404s.
    """
    if _need_tenant(request):
        return redirect("scm:salesorderallocation_list")
    line = get_object_or_404(
        SalesOrderLine.objects.select_related("item", "sales_order"),
        pk=line_pk, sales_order__tenant=request.tenant)
    order = line.sales_order
    if order.status not in order.ALLOCATABLE_STATUSES:
        messages.error(request, "Stock can only be allocated to a submitted order.")
        return redirect("scm:salesorder_detail", pk=order.pk)
    if line.item_id is None:
        messages.error(request, "Pick a stock item on this line before allocating against it.")
        return redirect("scm:salesorder_detail", pk=order.pk)

    if request.method == "POST":
        form = SalesOrderAllocationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            alloc = form.save(commit=False)
            alloc.tenant = request.tenant
            alloc.sales_order_line = line
            try:
                with transaction.atomic():
                    # Lock the ITEM row before reading availability. Without it the check and the
                    # write are separate statements, so two admins allocating the same item at the
                    # same moment both read "5 available" and both reserve 5 — 10 units promised
                    # against 5 on hand, with no error and nothing to show it happened (security
                    # review). The item is the right granularity: availability is per item+location
                    # ACROSS orders, so locking only this order's line would not serialize the
                    # racing pair.
                    _lock_item(line.item_id)
                    # Two guards, deliberately separate questions: full_clean runs the model's
                    # "not more than was ordered" rule, and the ATP check asks whether the stock is
                    # actually there. An order for 10 with 3 on hand fails the second, not the first.
                    alloc.full_clean(exclude=["sales_order_line", "tenant"])
                    available = _available_to_promise(line.item, alloc.location)
                    if alloc.quantity > available:
                        raise ValidationError({"quantity": (
                            f"Only {available} of {line.item.sku} can be promised at "
                            f"{alloc.location.code} — the rest is on hand but already reserved for "
                            f"another order. Allocate less, or pick another location.")})
                    alloc.save()
                    order.recompute_allocation_status()
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                write_audit_log(request.user, alloc, "create",
                                {"line": line.pk, "quantity": str(alloc.quantity)})
                messages.success(request, f"Reserved {alloc.quantity} at {alloc.location.code}.")
                return redirect("scm:salesorder_detail", pk=order.pk)
    else:
        form = SalesOrderAllocationForm(tenant=request.tenant,
                                        initial={"quantity": line.quantity_backordered()})
    return render(request, "scm/orders/salesorderallocation/form.html", {
        "form": form, "is_edit": False, "obj": None, "line": line, "order": order,
        "atp_rows": _atp_rows(request.tenant, line.item),
    })


@tenant_admin_required
def salesorderallocation_edit(request, pk):
    obj = get_object_or_404(
        SalesOrderAllocation.objects.select_related("sales_order_line__item", "sales_order_line__sales_order"),
        pk=pk, tenant=request.tenant)
    if obj.status != "reserved":
        messages.error(request, "Only a reserved allocation can be edited — cancel it instead.")
        return redirect("scm:salesorderallocation_detail", pk=pk)
    line = obj.sales_order_line
    order = line.sales_order
    if request.method == "POST":
        form = SalesOrderAllocationForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            alloc = form.save(commit=False)
            try:
                with transaction.atomic():
                    _lock_item(line.item_id)  # see the create path — same race, same lock
                    alloc.full_clean(exclude=["sales_order_line", "tenant"])
                    # exclude_pk: this row's own current reservation must not count against itself.
                    available = _available_to_promise(line.item, alloc.location, exclude_pk=alloc.pk)
                    if alloc.quantity > available:
                        raise ValidationError({"quantity": (
                            f"Only {available} of {line.item.sku} can be promised at "
                            f"{alloc.location.code}.")})
                    alloc.save()
                    order.recompute_allocation_status()
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                write_audit_log(request.user, alloc, "update", {"quantity": str(alloc.quantity)})
                messages.success(request, "Allocation updated.")
                return redirect("scm:salesorder_detail", pk=order.pk)
    else:
        form = SalesOrderAllocationForm(instance=obj, tenant=request.tenant)
    return render(request, "scm/orders/salesorderallocation/form.html", {
        "form": form, "is_edit": True, "obj": obj, "line": line, "order": order,
        "atp_rows": _atp_rows(request.tenant, line.item, exclude_pk=obj.pk),
    })


def _atp_rows(tenant, item, exclude_pk=None):
    """Available-to-promise per pickable location, so staff can see where the stock actually is
    before typing a quantity rather than guessing and being rejected.

    THREE queries total regardless of how many locations exist — the locations, one grouped on-hand,
    one grouped reservation total. Calling _available_to_promise per location instead would cost two
    aggregates each, and 4.4's bin model means a real warehouse has many pickable locations, not the
    two or three in the seed data (perf review).
    """
    if item is None:
        return []
    locations = list(Location.objects.filter(tenant=tenant, is_active=True,
                                             is_pickable=True).order_by("code"))
    if not locations:
        return []
    loc_ids = [l.pk for l in locations]
    on_hand_map = {
        r["location_id"]: (r["q"] or ZERO)
        for r in (item.stock_moves.filter(location_id__in=loc_ids)
                  .values("location_id").annotate(q=Sum("quantity")))
    }
    reserved_qs = (SalesOrderAllocation.objects
                   .filter(sales_order_line__item=item, location_id__in=loc_ids)
                   .exclude(status="cancelled"))
    if exclude_pk is not None:
        reserved_qs = reserved_qs.exclude(pk=exclude_pk)
    reserved_map = {
        r["location_id"]: (r["q"] or ZERO)
        for r in reserved_qs.values("location_id").annotate(q=Sum("quantity"))
    }
    rows = []
    for loc in locations:
        available = on_hand_map.get(loc.pk, ZERO) - reserved_map.get(loc.pk, ZERO)
        if available > ZERO:
            rows.append({"location": loc, "available": available})
    return rows


@tenant_admin_required
@require_POST
def salesorderallocation_release(request, pk):
    """Reserved -> released: handed to the warehouse. Still no StockMove, still counts as allocated."""
    obj = get_object_or_404(SalesOrderAllocation.objects.select_related("sales_order_line__sales_order"),
                            pk=pk, tenant=request.tenant)
    if obj.status != "reserved":
        messages.info(request, "Only a reserved allocation can be released.")
        return redirect("scm:salesorderallocation_detail", pk=pk)
    obj.status = "released"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "release"})
    messages.success(request, "Allocation released to the warehouse.")
    return redirect("scm:salesorderallocation_detail", pk=pk)


@tenant_admin_required
@require_POST
def salesorderallocation_cancel(request, pk):
    """Drop the claim. Frees the availability-to-promise; posts nothing, because nothing physical
    ever happened."""
    obj = get_object_or_404(SalesOrderAllocation.objects.select_related("sales_order_line__sales_order"),
                            pk=pk, tenant=request.tenant)
    if obj.status == "cancelled":
        messages.info(request, "This allocation is already cancelled.")
        return redirect("scm:salesorderallocation_detail", pk=pk)
    with transaction.atomic():
        obj.status = "cancelled"
        obj.save(update_fields=["status", "updated_at"])
        obj.sales_order_line.sales_order.recompute_allocation_status()
    write_audit_log(request.user, obj, "update", {"action": "cancel"})
    messages.success(request, "Allocation cancelled — the stock is available again.")
    return redirect("scm:salesorderallocation_detail", pk=pk)


@tenant_admin_required
@require_POST
def salesorderallocation_delete(request, pk):
    """Hard delete, only while still `reserved`.

    A released allocation must be CANCELLED, not deleted: the warehouse has already been told about
    it, so it needs to leave a visible cancelled row rather than vanish without trace.
    """
    obj = get_object_or_404(SalesOrderAllocation.objects.select_related("sales_order_line__sales_order"),
                            pk=pk, tenant=request.tenant)
    if obj.status != "reserved":
        messages.error(request, "Only a reserved allocation can be deleted — cancel it instead.")
        return redirect("scm:salesorderallocation_detail", pk=pk)
    order = obj.sales_order_line.sales_order
    with transaction.atomic():
        write_audit_log(request.user, obj, "delete", {"quantity": str(obj.quantity)})
        obj.delete()
        order.recompute_allocation_status()
    messages.success(request, "Allocation deleted.")
    return redirect("scm:salesorder_detail", pk=order.pk)
