"""SCM 4.5 Order Management System — SalesOrder views (capture → validate → allocate → fulfill)."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant
from apps.scm.forms._common import _customer_parties
from apps.scm.models import SalesOrder, SalesOrderAllocation
from apps.scm.forms import SalesOrderForm, SalesOrderLineFormSet

ZERO = Decimal("0")

# A first order from a brand-new customer above this value is worth a human look before it ships.
# A deliberately crude, explainable rule — ML fraud scoring is a hosted-service concern, and a rule
# staff can predict beats a black box that silently holds orders nobody can explain.
NEW_CUSTOMER_FRAUD_THRESHOLD = Decimal("5000.00")


def _evaluate_hold(order):
    """Decide whether this order should be held for credit or fraud. Returns (credit, fraud, reason).

    Lives in the view layer, NOT on the model: `apps.scm` models never cross-import a peer app, and
    this reads `accounting.CustomerProfile` + `accounting.Invoice`. That is the same place — and the
    same computation — as `accounting.views.AccountsReceivable.Invoices.invoice_detail`'s
    `over_limit` check, reused rather than reinvented.

    The order's OWN total counts toward the exposure: the question being asked is "should we commit
    to this order", so the answer has to include the order being committed to.
    """
    from apps.accounting.models import CustomerProfile, Invoice

    reasons = []
    credit_hold = False
    profile = CustomerProfile.objects.filter(tenant=order.tenant, party=order.customer).first()
    if profile is not None:
        if profile.credit_on_hold:
            credit_hold = True
            reasons.append("Customer account is on credit hold")
        elif profile.credit_limit:
            outstanding = (Invoice.objects.filter(tenant=order.tenant, party=order.customer,
                                                  status__in=Invoice.OPEN_STATUSES)
                           .aggregate(s=Sum("total"))["s"] or ZERO)
            exposure = outstanding + (order.total or ZERO)
            if exposure > profile.credit_limit:
                credit_hold = True
                reasons.append(
                    f"Credit limit exceeded — {exposure} exposure against a "
                    f"{profile.credit_limit} limit ({outstanding} already open)")

    # "First order" is judged by whether any OTHER order exists for this customer, so re-submitting
    # the same order after a hold is released doesn't re-trip the rule on itself.
    is_first_order = not (SalesOrder.objects
                          .filter(tenant=order.tenant, customer=order.customer)
                          .exclude(pk=order.pk).exists())
    fraud_flag = is_first_order and (order.total or ZERO) > NEW_CUSTOMER_FRAUD_THRESHOLD
    if fraud_flag:
        reasons.append(
            f"New customer's first order above {NEW_CUSTOMER_FRAUD_THRESHOLD} — confirm before shipping")
    return credit_hold, fraud_flag, "; ".join(reasons)


@login_required
def salesorder_list(request):
    qs = (SalesOrder.objects.filter(tenant=request.tenant)
          .select_related("customer", "currency", "invoice"))
    return crud_list(
        request, qs, "scm/orders/salesorder/list.html",
        search_fields=["number", "customer__name", "notes"],
        filters=[("status", "status", False), ("source_channel", "source_channel", False),
                 ("customer", "customer_id", True)],
        extra_context={
            "status_choices": SalesOrder.STATUS_CHOICES,
            "source_channel_choices": SalesOrder.SOURCE_CHANNEL_CHOICES,
            "customers": _customer_parties(request.tenant),
        },
    )


@login_required
def salesorder_create(request):
    return _salesorder_form(request, instance=None)


@login_required
def salesorder_edit(request, pk):
    obj = get_object_or_404(SalesOrder, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a draft order can be edited — it is a live commitment once submitted.")
        return redirect("scm:salesorder_detail", pk=pk)
    return _salesorder_form(request, instance=obj)


def _salesorder_form(request, instance):
    """Header + line formset saved in ONE transaction, then totals recomputed from the saved lines.

    Hand-rolled rather than crud_create/crud_edit because the formset has to commit with its parent;
    that bypass is also why `_changed` is imported explicitly, so the audit diff isn't lost.
    """
    if instance is None and _need_tenant(request):
        return redirect("scm:salesorder_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = SalesOrderForm(request.POST, instance=instance, tenant=request.tenant)
        formset = SalesOrderLineFormSet(request.POST, instance=instance,
                                        form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                order = form.save(commit=False)
                order.tenant = request.tenant
                order.save()
                formset.instance = order
                formset.save()
                # After the lines are committed, never before — recalc reads them back.
                order.recalc_totals()
            write_audit_log(request.user, order, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"Sales order {order.number} saved.")
            return redirect("scm:salesorder_detail", pk=order.pk)
    else:
        form = SalesOrderForm(instance=instance, tenant=request.tenant)
        formset = SalesOrderLineFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "scm/orders/salesorder/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def salesorder_detail(request, pk):
    obj = get_object_or_404(
        SalesOrder.objects.select_related("customer", "currency", "payment_terms", "invoice",
                                          "ship_to_address", "source_quote"),
        pk=pk, tenant=request.tenant)
    # One query for the lines, one for every allocation across them — then stitched in Python, so
    # the page cost stays flat instead of running an aggregate per line (the 4.3/4.4 lesson).
    lines = list(obj.lines.select_related("item"))
    allocations = list(SalesOrderAllocation.objects
                       .filter(sales_order_line__in=lines)
                       .select_related("location", "sales_order_line"))
    by_line = {}
    for alloc in allocations:
        by_line.setdefault(alloc.sales_order_line_id, []).append(alloc)
    rows = []
    for line in lines:
        line_allocs = by_line.get(line.pk, [])
        allocated = sum((a.quantity for a in line_allocs if a.status != "cancelled"), ZERO)
        ordered = line.quantity_ordered or ZERO
        backordered = ordered - allocated
        rows.append({
            "line": line,
            "allocations": line_allocs,
            "allocated": allocated,
            "backordered": backordered if backordered > ZERO else ZERO,
        })
    # Only queried for the one status that can actually use it — the mark-invoiced picker.
    linkable_invoices = []
    if obj.status == "fulfilled":
        from apps.accounting.models import Invoice
        linkable_invoices = list(Invoice.objects.filter(tenant=request.tenant, party=obj.customer)
                                 .order_by("-id")[:25])
    return render(request, "scm/orders/salesorder/detail.html", {
        "obj": obj,
        "rows": rows,
        "has_active_allocations": any(a.status != "cancelled" for a in allocations),
        "linkable_invoices": linkable_invoices,
    })


@login_required
@require_POST
def salesorder_delete(request, pk):
    obj = get_object_or_404(SalesOrder, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "Only a draft order can be deleted — cancel it instead.")
        return redirect("scm:salesorder_detail", pk=pk)
    return crud_delete(request, model=SalesOrder, pk=pk, success_url="scm:salesorder_list")


@login_required
@require_POST
def salesorder_submit(request, pk):
    """Draft -> submitted, or -> on_hold when credit/fraud validation trips.

    A held order is NOT confirmed to the customer: `confirmation_sent_at` is stamped only on the
    path that actually reaches `submitted`, so the notification record can't claim a confirmation
    that was never appropriate to send.
    """
    with transaction.atomic():
        obj = get_object_or_404(SalesOrder.objects.select_for_update().select_related("customer"),
                                pk=pk, tenant=request.tenant)
        if obj.status != "draft":
            messages.info(request, "This order has already been submitted.")
            return redirect("scm:salesorder_detail", pk=pk)
        if not obj.lines.exists():
            messages.error(request, "Add at least one line before submitting the order.")
            return redirect("scm:salesorder_detail", pk=pk)
        # A quote-converted line arrives with no stock item (see SalesOrderLine.item). Allocation,
        # picking and every on-hand check key off the item, so an unmapped line would be an order
        # nobody can fulfill — caught here, while it is still an editable draft.
        unmapped = [l.description or f"line {l.pk}" for l in obj.lines.all() if l.item_id is None]
        if unmapped:
            messages.error(request, (
                f"{len(unmapped)} line(s) still have no stock item picked: "
                f"{', '.join(unmapped[:3])}{'…' if len(unmapped) > 3 else ''}. "
                "Edit the order and map them before submitting."))
            return redirect("scm:salesorder_detail", pk=pk)
        obj.recalc_totals()  # validate against the CURRENT total, not a stale one
        credit_hold, fraud_flag, reason = _evaluate_hold(obj)
        obj.credit_hold, obj.fraud_flag, obj.hold_reason = credit_hold, fraud_flag, reason
        fields = ["status", "credit_hold", "fraud_flag", "hold_reason", "updated_at"]
        if credit_hold or fraud_flag:
            obj.status = "on_hold"
        else:
            obj.status = "submitted"
            if obj.confirmation_sent_at is None:
                obj.confirmation_sent_at = timezone.now()
                fields.append("confirmation_sent_at")
        if obj.order_date is None:
            obj.order_date = timezone.localdate()
            fields.append("order_date")
        obj.save(update_fields=fields)
    write_audit_log(request.user, obj, "update",
                    {"action": "submit", "status": obj.status, "hold_reason": obj.hold_reason})
    if obj.status == "on_hold":
        messages.warning(request, f"Order {obj.number} is on hold — {obj.hold_reason}.")
    else:
        messages.success(request, f"Order {obj.number} submitted.")
    return redirect("scm:salesorder_detail", pk=pk)


@tenant_admin_required
@require_POST
def salesorder_release_hold(request, pk):
    """Override a credit/fraud hold. Tenant-admin gated and requires a written reason.

    The reason is APPENDED to hold_reason rather than replacing it: why the order was held is part
    of the audit trail, and an override that erased its own justification would be worthless.
    """
    obj = get_object_or_404(SalesOrder, pk=pk, tenant=request.tenant)
    if obj.status != "on_hold":
        messages.info(request, "This order is not on hold.")
        return redirect("scm:salesorder_detail", pk=pk)
    note = (request.POST.get("release_note") or "").strip()
    if not note:
        messages.error(request, "Give a reason for releasing the hold.")
        return redirect("scm:salesorder_detail", pk=pk)
    obj.credit_hold = False
    obj.fraud_flag = False
    obj.hold_reason = f"{obj.hold_reason}\nReleased by {request.user}: {note}".strip()
    obj.status = "submitted"
    fields = ["credit_hold", "fraud_flag", "hold_reason", "status", "updated_at"]
    if obj.confirmation_sent_at is None:
        obj.confirmation_sent_at = timezone.now()
        fields.append("confirmation_sent_at")
    obj.save(update_fields=fields)
    write_audit_log(request.user, obj, "update", {"action": "release_hold", "note": note})
    messages.success(request, f"Hold released on {obj.number}.")
    return redirect("scm:salesorder_detail", pk=pk)


@tenant_admin_required
@require_POST
def salesorder_fulfill(request, pk):
    """Staff attestation that the order went out through the warehouse.

    There is no enforced FK back to a 4.4 PickTask this pass, so this records a human's statement
    rather than deriving fulfillment from picks. Named honestly for that reason — see the module
    skill's Deferred list.
    """
    obj = get_object_or_404(SalesOrder, pk=pk, tenant=request.tenant)
    if obj.status not in ("allocated", "partially_fulfilled"):
        messages.error(request, "Only an allocated order can be marked fulfilled.")
        return redirect("scm:salesorder_detail", pk=pk)
    obj.status = "fulfilled"
    obj.shipped_notification_at = timezone.now()
    obj.save(update_fields=["status", "shipped_notification_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "fulfill"})
    messages.success(request, f"Order {obj.number} marked fulfilled.")
    return redirect("scm:salesorder_detail", pk=pk)


@login_required
@require_POST
def salesorder_mark_delivered(request, pk):
    """Stamp the delivery notification hook. Deliberately does NOT change status — delivery is not
    part of this model's commercial lifecycle, and pretending otherwise would invent a state that
    nothing derives from."""
    obj = get_object_or_404(SalesOrder, pk=pk, tenant=request.tenant)
    if obj.shipped_notification_at is None:
        messages.error(request, "Mark the order fulfilled before recording delivery.")
        return redirect("scm:salesorder_detail", pk=pk)
    obj.delivered_notification_at = timezone.now()
    obj.save(update_fields=["delivered_notification_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "mark_delivered"})
    messages.success(request, f"Delivery recorded for {obj.number}.")
    return redirect("scm:salesorder_detail", pk=pk)


@login_required
@require_POST
def salesorder_mark_invoiced(request, pk):
    """Link the AR invoice and mark the order invoiced, in one step.

    The invoice is chosen HERE rather than on the order form. It used to be an ordinary form field,
    which made this action unreachable: the form is editable only while the order is `draft`, but
    this action requires `fulfilled`, so the two conditions could never both hold — and in real life
    the invoice does not exist until after fulfillment anyway. Accepting it on the POST is what makes
    the AR hand-off actually work (code review).
    """
    obj = get_object_or_404(SalesOrder, pk=pk, tenant=request.tenant)
    if obj.status != "fulfilled":
        messages.error(request, "Only a fulfilled order can be marked invoiced.")
        return redirect("scm:salesorder_detail", pk=pk)
    invoice_pk = (request.POST.get("invoice") or "").strip()
    fields = ["status", "updated_at"]
    if invoice_pk:
        from apps.accounting.models import Invoice
        # Tenant-scoped lookup, so a crafted pk can't attach another workspace's invoice.
        invoice = Invoice.objects.filter(pk=invoice_pk, tenant=request.tenant).first()
        if invoice is None:
            messages.error(request, "That invoice doesn't exist in this workspace.")
            return redirect("scm:salesorder_detail", pk=pk)
        obj.invoice = invoice
        fields.append("invoice")
    if obj.invoice_id is None:
        messages.error(request, "Pick the accounting invoice to link before marking the order invoiced.")
        return redirect("scm:salesorder_detail", pk=pk)
    obj.status = "invoiced"
    obj.save(update_fields=fields)
    write_audit_log(request.user, obj, "update", {"action": "mark_invoiced", "invoice": obj.invoice_id})
    messages.success(request, f"Order {obj.number} marked invoiced.")
    return redirect("scm:salesorder_detail", pk=pk)


@tenant_admin_required
@require_POST
def salesorder_cancel(request, pk):
    """Cancel an order that hasn't shipped. Blocked while stock is still reserved for it.

    Mirrors purchaseorder_cancel refusing while receipts exist: an executing commitment must be
    un-allocated deliberately, never cancelled out from under a reservation the warehouse may
    already be picking against.
    """
    obj = get_object_or_404(SalesOrder, pk=pk, tenant=request.tenant)
    if obj.status in ("fulfilled", "invoiced", "cancelled", "closed"):
        messages.error(request, "This order has already shipped or closed and can't be cancelled.")
        return redirect("scm:salesorder_detail", pk=pk)
    reason = (request.POST.get("cancel_reason") or "").strip()
    if not reason:
        messages.error(request, "Give a reason for cancelling the order.")
        return redirect("scm:salesorder_detail", pk=pk)
    if obj.has_active_allocations():
        messages.error(request, (
            "This order still has stock allocated to it — cancel its allocations first, "
            "so the reserved stock is visibly released rather than silently dropped."))
        return redirect("scm:salesorder_detail", pk=pk)
    obj.status = "cancelled"
    obj.notes = f"{obj.notes}\nCancelled by {request.user}: {reason}".strip()
    obj.save(update_fields=["status", "notes", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "cancel", "reason": reason})
    messages.success(request, f"Order {obj.number} cancelled.")
    return redirect("scm:salesorder_detail", pk=pk)


@login_required
@require_POST
def salesorder_close(request, pk):
    obj = get_object_or_404(SalesOrder, pk=pk, tenant=request.tenant)
    if obj.status != "invoiced":
        messages.error(request, "Only an invoiced order can be closed.")
        return redirect("scm:salesorder_detail", pk=pk)
    obj.status = "closed"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "close"})
    messages.success(request, f"Order {obj.number} closed.")
    return redirect("scm:salesorder_detail", pk=pk)


@login_required
@require_POST
def salesorder_create_from_quote(request, quote_pk):
    """Turn an accepted CRM quote into a draft sales order.

    This closes a real dead end: `crm.Quote.quote_accept()` flips a status and creates nothing
    downstream, so an accepted quote had nowhere to go. The FIRST import from scm into crm models —
    precedented one layer over by `forms/_common.py` importing `accounting.Currency`.

    Item mapping is deliberately NOT guessed. `crm.QuoteLine.product` is a CRM `Product`, a
    different table from `scm.Item` with no mapping between them; inventing one by name would
    quietly attach orders to the wrong stock. Instead each line carries the quote's `description`
    across so nothing is lost, leaves `item` blank, and the user lands on the edit form to pick the
    real items before submitting.
    """
    from apps.accounting.models import Currency
    from apps.crm.models import Quote

    quote = get_object_or_404(Quote, pk=quote_pk, tenant=request.tenant)
    if quote.status != "accepted":
        messages.error(request, "Only an accepted quote can be converted to a sales order.")
        return redirect("crm:quote_detail", pk=quote_pk)
    existing = SalesOrder.objects.filter(tenant=request.tenant, source_quote=quote).first()
    if existing is not None:
        messages.info(request, f"This quote was already converted to {existing.number}.")
        return redirect("scm:salesorder_detail", pk=existing.pk)

    with transaction.atomic():
        # The quote's account only becomes the order's customer if it actually carries the customer
        # role — an account tagged only as a lead would otherwise silently become a customer.
        customer = None
        if quote.account_id and quote.account.roles.filter(role="customer").exists():
            customer = quote.account
        if customer is None:
            messages.error(request, (
                "The quote's account isn't marked as a customer — add the customer role to "
                f"{quote.account.name if quote.account_id else 'the account'} first."))
            return redirect("crm:quote_detail", pk=quote_pk)
        order = SalesOrder(
            tenant=request.tenant, customer=customer, source_quote=quote,
            source_channel="manual", order_date=timezone.localdate(),
            # Quote.currency_code is a plain 3-letter string; SalesOrder.currency is an FK.
            currency=Currency.objects.filter(code=quote.currency_code).first(),
            notes=f"Converted from quote {quote.number}.",
        )
        order.save()
        line_model = order.lines.model
        line_model.objects.bulk_create([
            line_model(
                sales_order=order,
                item=None,  # see SalesOrderLine.item — mapped by hand, never guessed
                description=qline.description,
                quantity_ordered=qline.quantity or Decimal("1"),
                unit_price=qline.unit_price or ZERO,
                discount_pct=qline.discount_pct or ZERO,
                tax_pct=qline.tax_pct or ZERO,
            )
            for qline in quote.lines.all()
        ])
        order.recalc_totals()
    write_audit_log(request.user, order, "create", {"action": "from_quote", "quote": quote.number})
    messages.success(request, (
        f"Draft order {order.number} created from {quote.number}. "
        "Pick the stock item on each line before submitting — quote products don't map automatically."))
    return redirect("scm:salesorder_edit", pk=order.pk)
