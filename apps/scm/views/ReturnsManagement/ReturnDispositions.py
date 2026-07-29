"""SCM 4.10 Returns Management — the receiving bench, and 4.10's ONLY stock posting.

``returndisposition_post`` is the one action in the whole sub-module that writes to the append-only
ledger, and it does so exactly once per row, for exactly two shapes:

* ``restock`` (or a refurbished row being restocked) → ONE **positive** ``receipt`` StockMove into
  ``restock_location`` at ``restock_unit_cost``, carrying ``reference=RMA-…``.
* ``scrap`` / ``donate`` / ``recycle`` / ``liquidate`` **on a row that already posted** → ONE
  **negative** ``adjustment`` out of the same location. Straight off the bench these post NOTHING,
  because the goods never entered stock in the first place.

Everything else — ``return_to_vendor``, ``repair_return``, ``quarantine``, ``credit_only`` and
intake itself — posts nothing, ever. That is :attr:`ReturnDisposition.posts_stock`, an EXECUTABLE
rule the action asks rather than a comment somebody has to remember.

**Why ``receipt`` and not ``issue``:** 4.7's ``demand_series`` filters ``move_type="issue"`` ONLY
and NEGATES the signed sum, so a positive ``issue`` would SUBTRACT from a historical demand bucket
and silently deflate every forecast built on stock issues. A consequence of that choice, said out
loud: **demand history stays GROSS** — returns are not netted out of it. That is a 4.11 change to
``models/DemandPlanning/_history.py``.

**The cost trap this module is built around.** ``_post_stock_move`` calls
``item.apply_receipt(quantity, unit_cost)`` for ANY positive quantity, and ``apply_receipt`` rolls
the cached weighted average against PRE-move on-hand. ``ReturnLine.unit_price`` is the SALE price —
restocking at it would roll ``average_cost`` up toward the selling price and overstate
``Item.total_value()`` and the ``weighted_avg`` branch of the valuation report. Hence
``restock_unit_cost``, seeded from the grade write-down and never the price.

**§3.4's ``_shared_items()`` rule, and why this module structurally does not need it.** The rule
says a MULTI-ROW same-item receipt must share ONE ``Item`` instance across its rows, because
``select_related("item")`` hands back a separate object per row and the second row's
weighted-average roll would then be computed from pre-first-row state, silently corrupting
``average_cost``. Every existing multi-line poster (``_post_transfer``, ``_post_pick``,
``_post_adjustment``) obeys it. **The bench deliberately posts exactly ONE row per action**:
``returndisposition_post`` takes a single pk, opens its own transaction and re-reads that row's
``Item`` from the database, so two rows for the same item are two transactions and the second one
sees the first one's committed ``average_cost``. There is no multi-row posting path in 4.10 — and
if one is ever added (a "post the whole bench" button), it MUST route its rows through
``_shared_items`` before calling ``_post_stock_move``.
"""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import (_acting_party, _date_window, _insufficient_stock, _is_tenant_admin,
                                     _item_qs, _location_qs, _need_tenant, _post_stock_move)
from apps.scm.models._base import q4
from apps.scm.models import LotSerial, ReturnDisposition, ReturnLine, StockMove, select_policy
from apps.scm.forms import (ReturnDispositionDecideForm, ReturnDispositionForm,
                            ReturnDispositionFormSet, ReturnDispositionSplitForm,
                            ReturnLinePickerForm)

ZERO = Decimal("0")


def _bench_queryset(tenant):
    """Every FK a bench row renders, joined once.

    ``return_line__return_authorization__customer`` because the row shows whose return it is, and
    ``lot_serial__item`` because ``LotSerial.__str__`` reads ``item.sku`` (§7.6 — the rendered row
    has the same one-query-per-object problem a dropdown does).
    """
    return (ReturnDisposition.objects.filter(tenant=tenant)
            .select_related("return_line__return_authorization__customer",
                            "return_line__item__uom", "return_line__reason",
                            "location", "restock_location", "lot_serial__item",
                            "received_by", "decided_by", "nonconformance", "stock_move"))


@login_required
def returndisposition_list(request):
    """The receiving bench.

    Note the ``credit_only`` branch in ``stats``: a credit-only RMA never produces a row here, so a
    bench whose counters were derived from rows alone would say "nothing outstanding" while a queue
    of credit-only returns waits in the refund queue. §7.11 — it is counted separately and named.
    """
    qs = _bench_queryset(request.tenant)
    qs = _date_window(qs, request.GET, "received_on")
    if request.GET.get("pending", "").strip() == "yes":
        qs = qs.filter(disposition="received_pending")
    if request.GET.get("unposted", "").strip() == "yes":
        # The SQL half of "would move stock and has not". It must agree with the per-row badge
        # (§7.5), and there are THREE shapes the row renders, not two: the third — a refurbished
        # row that is ready to go back — was missing, so a unit sitting refurbished and ready was
        # invisible to the page whose whole job is "what still needs posting?", while the row
        # itself said "ready to post". It then never gets posted, never valued and never sold.
        # Mirrors the corrected `can_restock_after_refurbish` clause for clause.
        qs = qs.filter(
            Q(disposition="restock", stock_posted=False, restock_location__isnull=False)
            | Q(disposition__in=ReturnDisposition.WRITE_OFF_DISPOSITIONS, stock_posted=True,
                restock_location__isnull=False)
            | Q(disposition="refurbish", refurbished_on__isnull=False, stock_posted=False,
                restock_location__isnull=False))
    stats = ReturnDisposition.objects.filter(tenant=request.tenant).aggregate(
        pending=Count("id", filter=Q(disposition="received_pending")),
        restocked=Count("id", filter=Q(disposition="restock", stock_posted=True)),
        awaiting_post=Count("id", filter=Q(disposition="restock", stock_posted=False)),
        refurbishing=Count("id", filter=Q(disposition="refurbish", refurbished_on__isnull=True)),
        written_off=Count("id", filter=Q(
            disposition__in=ReturnDisposition.WRITE_OFF_DISPOSITIONS)),
        quantity_on_bench=Sum("quantity", filter=Q(disposition="received_pending")),
    )
    return crud_list(
        request, qs, "scm/returns/returndisposition/list.html",
        search_fields=["notes", "return_line__item__sku", "return_line__item__name",
                       "return_line__return_authorization__number", "lot_serial__number"],
        filters=[("disposition", "disposition", False),
                 ("condition_grade", "condition_grade", False),
                 ("location", "location_id", True),
                 ("restock_location", "restock_location_id", True),
                 ("item", "return_line__item_id", True),
                 ("stock_posted", "stock_posted", False)],
        extra_context={
            "disposition_choices": ReturnDisposition.DISPOSITION_CHOICES,
            "grade_choices": ReturnDisposition.GRADE_CHOICES,
            "locations": _location_qs(request.tenant),
            "items": _item_qs(request.tenant),
            "stats": stats,
            # §7.11: what the bench cannot see. Named on the page rather than left to be
            # discovered — a credit-only return is real work with no bench row.
            "credit_only_waiting": _credit_only_waiting(request.tenant),
        },
    )


def _credit_only_waiting(tenant):
    """Credit-only RMAs that will never appear on the bench — §7.11's visible half."""
    from apps.scm.models import ReturnAuthorization
    return (ReturnAuthorization.objects
            .filter(tenant=tenant, return_type="credit_only", credit_note__isnull=True)
            .exclude(status__in=("draft", "requested", "rejected", "cancelled"))
            .select_related("customer")[:10])


@login_required
def returndisposition_create(request):
    """Receive one or more rows against ONE return line.

    §7.1, place (b), in its most literal form: the picker form is validated FIRST, its chosen line
    is assigned to ``formset.instance``, and only THEN is ``formset.is_valid()`` called. Without
    that order ``BaseReturnDispositionFormSet.clean()``'s ``sum(quantity) <= quantity_approved`` cap
    reads an empty ``ReturnLine()`` whose ``quantity_approved`` is None and passes everything.
    """
    if _need_tenant(request):
        return redirect("scm:returndisposition_list")
    picked = None
    if request.method == "POST":
        picker = ReturnLinePickerForm(request.POST, tenant=request.tenant)
        picker_ok = picker.is_valid()
        picked = picker.cleaned_data["return_line"] if picker_ok else None
        formset = ReturnDispositionFormSet(request.POST, instance=picked,
                                           form_kwargs={"tenant": request.tenant})
        if picker_ok:
            formset.instance = picked      # ← load-bearing; see the docstring
        if picker_ok and formset.is_valid():
            party = _acting_party(request)
            with transaction.atomic():
                formset.instance = picked
                rows = formset.save(commit=False)
                for row in rows:
                    row.tenant = request.tenant
                    row.return_line = picked
                    if row.received_on is None:
                        row.received_on = timezone.localdate()
                    if row.received_by_id is None:
                        row.received_by = party
                    if row.is_decided and row.decided_on is None:
                        row.decided_on = timezone.localdate()
                        row.decided_by = party
                    row.save()
                _refresh_rma_status(picked.return_authorization_id)
            write_audit_log(request.user, picked.return_authorization, "update",
                            {"action": "receive", "line": str(picked), "rows": len(rows)})
            messages.success(request, f"{len(rows)} row(s) received against {picked}.")
            messages.info(request, "Nothing was posted to the stock ledger — the returns bench is "
                                   "deliberately off-ledger until a row is dispositioned.")
            return redirect("scm:returndisposition_list")
    else:
        line_id = (request.GET.get("line") or "").strip()
        if line_id.isdigit():
            picked = (ReturnLine.objects
                      .filter(pk=int(line_id),
                              return_authorization__tenant=request.tenant).first())
        picker = ReturnLinePickerForm(tenant=request.tenant,
                                      initial={"return_line": picked} if picked else None)
        formset = ReturnDispositionFormSet(instance=picked,
                                           form_kwargs={"tenant": request.tenant})
    return render(request, "scm/returns/returndisposition/form.html", {
        "picker": picker, "formset": formset, "is_edit": False, "line": picked, "obj": None})


@login_required
def returndisposition_edit(request, pk):
    """Edit ONE bench row. Refused outright once the row has posted to the ledger.

    The form disables ``quantity``/``disposition`` on a posted row as well (§7.5 — the gate lives
    in the view AND on the control), so a crafted POST that reached the form still cannot rewrite
    what the append-only ledger recorded.
    """
    obj = get_object_or_404(_bench_queryset(request.tenant), pk=pk)
    # `stock_move_id`, NOT `stock_posted`: after a restock-then-write-off the latch is set back
    # to False (correctly — the unit is no longer IN stock), but the row has by then written TWO
    # movements into an append-only ledger. Keying this guard on the latch re-opened edit and
    # delete on the only audit record linking those movements to the RMA. `stock_move` is set by
    # either posting and never cleared, so it is the honest "has ever touched the ledger" test.
    if obj.stock_move_id is not None:
        messages.error(request, "This row has already posted to the stock ledger — the ledger is "
                                "append-only, so its quantity and decision are history. Raise a "
                                "stock adjustment if the figures are wrong.")
        return redirect("scm:returndisposition_detail", pk=pk)
    if request.method == "POST":
        form = ReturnDispositionForm(request.POST, instance=obj, tenant=request.tenant,
                                     is_tenant_admin=_is_tenant_admin(request.user))
        if form.is_valid():
            with transaction.atomic():
                row = form.save(commit=False)
                row.tenant = request.tenant
                if row.is_decided and row.decided_on is None:
                    row.decided_on = timezone.localdate()
                    row.decided_by = _acting_party(request)
                row.save()
                _refresh_rma_status(row.return_line.return_authorization_id)
            write_audit_log(request.user, row, "update", _changed(form))
            messages.success(request, "Bench row updated.")
            return redirect("scm:returndisposition_detail", pk=row.pk)
    else:
        form = ReturnDispositionForm(instance=obj, tenant=request.tenant,
                                     is_tenant_admin=_is_tenant_admin(request.user))
    return render(request, "scm/returns/returndisposition/form.html", {
        "form": form, "is_edit": True, "obj": obj,
        "line": obj.return_line, "picker": None, "formset": None})


@login_required
def returndisposition_detail(request, pk):
    obj = get_object_or_404(_bench_queryset(request.tenant), pk=pk)
    line = obj.return_line
    policy = (line.return_authorization.policy
              or select_policy(request.tenant, line.item if line.item_id else None))
    return render(request, "scm/returns/returndisposition/detail.html", {
        "obj": obj,
        "line": line,
        "rma": line.return_authorization,
        "policy": policy,
        # Shown NEXT TO restock_unit_cost so an outlier is visible rather than merely possible.
        "item_average_cost": (line.item.average_cost or ZERO) if line.item_id else ZERO,
        "suggested_restock_cost": (
            policy.restock_cost_for(obj.condition_grade,
                                    line.item.average_cost if line.item_id else ZERO)
            if policy is not None else ZERO),
        # The ledger rows THIS return wrote — `reference` is the only link StockMove keeps to its
        # source document, exactly as the transfer/work-order/NCR detail pages do it.
        "moves": (StockMove.objects
                  .filter(tenant=request.tenant, reference=line.return_authorization.number)
                  .select_related("item", "location", "lot_serial")[:50]),
        "sibling_rows": (obj.return_line.dispositions.exclude(pk=obj.pk)
                         .select_related("location", "restock_location")),
        "decide_form": ReturnDispositionDecideForm(
            tenant=request.tenant, line=line,
            initial={
                "disposition": (line.reason.suggested_disposition
                                if line.reason_id and line.reason.suggested_disposition
                                else None),
                "condition_grade": obj.condition_grade,
                "restock_location": obj.restock_location_id,
                "restock_unit_cost": obj.restock_unit_cost,
            }),
        "split_form": ReturnDispositionSplitForm(row=obj),
        # A DATA-DRIVEN button, not a hard-coded reason list: the template offers "Raise a
        # non-conformance" only when the line's own reason says so. It links to 4.9's existing
        # nonconformance_create page rather than inventing a fourth conversion action here — and
        # the NCR is then linked back through this row's `nonconformance` FK. 4.9's
        # NonConformance.source stays "inspection": `source` is CharField(max_length=14) and
        # "customer_return" is 15 chars, so a new value is a column widen against a 4.9 model and
        # 4.10 does not carry one.
        "can_raise_ncr": bool(line.reason_id and line.reason.raises_nonconformance
                              and obj.nonconformance_id is None),
    })


@login_required
@require_POST
def returndisposition_delete(request, pk):
    obj = get_object_or_404(ReturnDisposition.objects.select_related("return_line"),
                            pk=pk, tenant=request.tenant)
    # `stock_move_id`, NOT `stock_posted`: after a restock-then-write-off the latch is set back
    # to False (correctly — the unit is no longer IN stock), but the row has by then written TWO
    # movements into an append-only ledger. Keying this guard on the latch re-opened edit and
    # delete on the only audit record linking those movements to the RMA. `stock_move` is set by
    # either posting and never cleared, so it is the honest "has ever touched the ledger" test.
    if obj.stock_move_id is not None:
        messages.error(request, "This row posted to the append-only stock ledger and cannot be "
                                "deleted — the movement it recorded really happened.")
        return redirect("scm:returndisposition_detail", pk=pk)
    rma_id = obj.return_line.return_authorization_id
    response = crud_delete(request, model=ReturnDisposition, pk=pk,
                           success_url="scm:returndisposition_list")
    _refresh_rma_status(rma_id)
    return response


# ============================================================= the bench decision (this can post)
def _refresh_rma_status(rma_id):
    """Move the parent RMA between ``awaiting_receipt`` / ``partially_received`` / ``received``.

    Derived from what the rows actually say, in the shape of
    ``SalesOrder.recompute_allocation_status()``: a status nobody typed cannot disagree with the
    quantities. Leaves settled/closed/cancelled/rejected alone — those are decisions, not derived
    state.
    """
    from apps.scm.models import ReturnAuthorization
    rma = (ReturnAuthorization.objects.filter(pk=rma_id)
           .prefetch_related("lines__dispositions").first())
    if rma is None or rma.status not in ("approved", "awaiting_receipt", "partially_received",
                                         "received"):
        return
    received = rma.quantity_received_total
    if received <= ZERO:
        new = "awaiting_receipt"
    elif rma.is_fully_received:
        new = "received"
    else:
        new = "partially_received"
    if new != rma.status:
        rma.status = new
        rma.save(update_fields=["status", "updated_at"])


@tenant_admin_required
@require_POST
def returndisposition_decide(request, pk):
    """Record the bench decision. Posts NOTHING — posting is a separate, explicit act.

    Splitting decide from post is what makes ``stock_posted`` trustworthy: the grader decides, and
    somebody with the stock authority presses Post. It also means a mis-decided row can be
    corrected right up until the moment the ledger sees it.

    Tenant-admin gated: the decision is what determines whether the customer's goods become
    sellable stock or a write-off.
    """
    # §7.8 — tenant first, form second.
    get_object_or_404(ReturnDisposition.objects.only("pk"), pk=pk, tenant=request.tenant)
    row = get_object_or_404(
        ReturnDisposition.objects.select_related("return_line__reason", "return_line__item"),
        pk=pk, tenant=request.tenant)
    form = ReturnDispositionDecideForm(request.POST, tenant=request.tenant, line=row.return_line)
    if not form.is_valid():
        messages.error(request, "; ".join(" ".join(errors) for errors in form.errors.values()))
        return redirect("scm:returndisposition_detail", pk=pk)
    disposition = form.cleaned_data["disposition"]
    grade = form.cleaned_data.get("condition_grade") or row.condition_grade
    restock_location = form.cleaned_data.get("restock_location")
    restock_cost = form.cleaned_data.get("restock_unit_cost")
    recovery = form.cleaned_data.get("recovery_value")
    note = (form.cleaned_data.get("notes") or "").strip()

    with transaction.atomic():
        obj = get_object_or_404(
            ReturnDisposition.objects.select_for_update()
            .select_related("return_line__reason", "return_line__item",
                            "return_line__return_authorization__policy", "lot_serial"),
            pk=pk, tenant=request.tenant)
        # Idempotency/terminal guard re-read INSIDE the lock: a posted row is an audit record.
        if obj.stock_posted and disposition == "restock":
            messages.info(request, "This row has already been restocked.")
            return redirect("scm:returndisposition_detail", pk=pk)
        line = obj.return_line
        # blocks_restock re-checked INSIDE the transaction, not only in the form (§7.5).
        if disposition == "restock" and line.reason_id and line.reason.blocks_restock:
            messages.error(request, f"Reason '{line.reason.code}' blocks restocking — this unit "
                                    "can never go back into sellable stock.")
            return redirect("scm:returndisposition_detail", pk=pk)
        if disposition == "restock" and restock_location is None:
            messages.error(request, "Choose where the unit goes back into sellable stock.")
            return redirect("scm:returndisposition_detail", pk=pk)
        if disposition == "restock" and restock_location is not None \
                and restock_location.pk == obj.location_id:
            messages.error(request, "That is the returns bench — a restock has to move the unit "
                                    "into sellable stock, not leave it where it is.")
            return redirect("scm:returndisposition_detail", pk=pk)
        if (disposition == "restock" and obj.lot_serial_id
                and obj.lot_serial.status == "expired"):
            messages.error(request, f"Lot {obj.lot_serial.number} is expired — scrap or quarantine "
                                    "it instead of restocking it.")
            return redirect("scm:returndisposition_detail", pk=pk)

        obj.disposition = disposition
        obj.condition_grade = grade
        fields = ["disposition", "condition_grade", "decided_on", "decided_by", "updated_at"]
        if restock_location is not None:
            obj.restock_location = restock_location
            fields.append("restock_location")
        if restock_cost is not None:
            obj.restock_unit_cost = q4(restock_cost)
            fields.append("restock_unit_cost")
        elif not obj.restock_unit_cost:
            # Re-seed from the grade write-down when the grader left it blank — SEEDED, then
            # human-owned. Nothing recomputes it afterwards.
            policy = (line.return_authorization.policy
                      or select_policy(request.tenant, line.item if line.item_id else None))
            if policy is not None and line.item_id:
                obj.restock_unit_cost = policy.restock_cost_for(grade, line.item.average_cost)
                fields.append("restock_unit_cost")
        if recovery is not None:
            obj.recovery_value = recovery
            fields.append("recovery_value")
        if note:
            obj.notes = note[:255]
            fields.append("notes")
        obj.decided_on = timezone.localdate()
        obj.decided_by = _acting_party(request)
        obj.save(update_fields=list(dict.fromkeys(fields)))

        # Quarantine posts NOTHING and flips the LOT's status instead — 4.9's ruling (b), applied
        # unchanged. The goods have not moved; on-hand is always Sum(quantity) over the ledger, so
        # a stored "blocked quantity" would be a second source of truth.
        lot_note = _flip_lot_for(obj, disposition)

    write_audit_log(request.user, obj, "update",
                    {"action": "decide", "disposition": disposition, "grade": grade})
    messages.success(request, f"Row dispositioned as {obj.get_disposition_display().lower()}.")
    if lot_note:
        messages.info(request, lot_note)
    if obj.posts_stock:
        messages.info(request, "Press Post to write this to the stock ledger — nothing has moved "
                               "yet.")
    elif disposition == "refurbish":
        messages.info(request, "Mark it refurbished when the work is done; that unlocks the same "
                               "restock action on this row.")
    elif disposition == "return_to_vendor":
        messages.info(request, "Nothing was posted — our stock never re-entered. Raise a warranty "
                               "claim from the return to chase the value.")
    elif disposition == "repair_return":
        messages.info(request, "Nothing was posted — the unit goes back to the customer, so it was "
                               "never our stock.")
    return redirect("scm:returndisposition_detail", pk=pk)


def _flip_lot_for(row, disposition):
    """Move the affected lot's status to match the decision. Posts NO StockMove.

    ``LotSerial.status`` had no writer on a restock anywhere in this app before 4.10: a serialised
    unit that was sold and shipped is ``consumed``, so restocking it posted a positive move and left
    the status saying it was gone — the ledger and the status disagreeing about the same unit.

    * ``restock``   → ``available`` (only from ``consumed``/``quarantine``; an expired lot is
                      refused upstream)
    * ``quarantine``→ ``quarantine``
    * write-offs    → ``consumed``

    Called INSIDE the caller's transaction. Returns a message or "".
    """
    if row.lot_serial_id is None:
        return ""
    target = None
    if disposition == "restock":
        target = "available"
    elif disposition == "quarantine":
        target = "quarantine"
    elif disposition in ReturnDisposition.CONSUMING_DISPOSITIONS:
        target = "consumed"
    if target is None:
        return ""
    # The lock is on the LOT, not the row: two returns touching the same batch at once is the race
    # that matters (the `_flip_lot_status` reasoning in 4.9, unchanged).
    lot = (LotSerial.objects.select_for_update()
           .filter(pk=row.lot_serial_id, tenant_id=row.tenant_id).first())
    if lot is None or lot.status == target:
        return ""
    if target == "available" and lot.status == "expired":
        return f"Lot {lot.number} is expired and was left as it is."
    previous = lot.get_status_display()
    lot.status = target
    lot.save(update_fields=["status", "updated_at"])
    return (f"Lot {lot.number} moved from {previous.lower()} to "
            f"{lot.get_status_display().lower()}. No stock movement was posted for that — a lot "
            "status is not a quantity.")


@tenant_admin_required
@require_POST
def returndisposition_post(request, pk):
    """Write this row to the append-only stock ledger. **The recipe in §7.9, verbatim.**

    1. ``@tenant_admin_required`` + ``@require_POST``
    2. tenant-scoped ``get_object_or_404`` before anything else (§7.8)
    3. no payload to validate — the decision is already on the row
    4. ``transaction.atomic()`` with a ``select_for_update()`` re-read
    5. terminal-state guard
    6. **idempotency re-read of ``stock_posted`` INSIDE the lock** — not before it. A double POST
       into an append-only ledger writes a second movement that can never be corrected in place.
    7. ``_insufficient_stock()`` → ``_post_stock_move()``, catching ``ValidationError``
    8. narrow ``save(update_fields=…)``
    9. ``write_audit_log`` after the writes
    10. branch-specific messages
    """
    get_object_or_404(ReturnDisposition.objects.only("pk"), pk=pk, tenant=request.tenant)
    posted_move = None
    try:
        with transaction.atomic():
            obj = get_object_or_404(
                ReturnDisposition.objects.select_for_update()
                .select_related("return_line__item", "return_line__reason",
                                "return_line__return_authorization", "location",
                                "restock_location", "lot_serial"),
                pk=pk, tenant=request.tenant)
            line = obj.return_line
            rma = line.return_authorization
            if rma.status in ("cancelled", "rejected"):
                messages.error(request, f"{rma.number} is {rma.get_status_display().lower()} — "
                                        "nothing may be posted against it.")
                return redirect("scm:returndisposition_detail", pk=pk)
            if obj.disposition == "received_pending":
                messages.error(request, "Decide what happens to this unit before posting it.")
                return redirect("scm:returndisposition_detail", pk=pk)
            # ---- 6. THE idempotency re-read, inside the lock ---------------------------------
            restocking = obj.disposition == "restock" or obj.can_restock_after_refurbish
            if restocking and obj.stock_posted:
                messages.info(request, "This row has already been posted to the stock ledger.")
                return redirect("scm:returndisposition_detail", pk=pk)
            if not obj.posts_stock and not obj.can_restock_after_refurbish:
                messages.info(
                    request,
                    f"A {obj.get_disposition_display().lower()} disposition has no ledger effect — "
                    "see the returns bench notes for why intake and non-restock decisions post "
                    "nothing.")
                return redirect("scm:returndisposition_detail", pk=pk)
            # blocks_restock, re-checked INSIDE atomic() — the form is a convenience (§7.5).
            if restocking and line.reason_id and line.reason.blocks_restock:
                messages.error(request, f"Reason '{line.reason.code}' blocks restocking.")
                return redirect("scm:returndisposition_detail", pk=pk)

            quantity = q4(obj.quantity or ZERO)
            item = line.item
            reference = rma.number
            if restocking:
                # POSITIVE receipt at the GRADED cost — never at unit_price. ONE row per call, so
                # the §3.4 shared-Item rule is satisfied by construction (see the module docstring).
                posted_move = _post_stock_move(
                    request.tenant, item=item, location=obj.restock_location,
                    quantity=quantity, move_type="receipt",
                    unit_cost=q4(obj.restock_unit_cost or ZERO), lot_serial=obj.lot_serial,
                    reference=reference,
                    reason=f"Return restock — grade {obj.condition_grade.upper()}")
                obj.stock_posted = True
            else:
                # A write-off of a unit that HAD been restocked: take it back out of the location
                # it was put into, guarded so it can never drive that location negative.
                shortfall = _insufficient_stock(item, obj.restock_location, quantity,
                                                obj.lot_serial)
                if shortfall:
                    raise ValidationError(shortfall)
                posted_move = _post_stock_move(
                    request.tenant, item=item, location=obj.restock_location,
                    quantity=-quantity, move_type="adjustment",
                    unit_cost=q4(obj.restock_unit_cost or ZERO), lot_serial=obj.lot_serial,
                    reference=reference,
                    reason=f"Return write-off — {obj.get_disposition_display()}")
                obj.stock_posted = False
            obj.stock_move = posted_move
            obj.save(update_fields=["stock_posted", "stock_move", "updated_at"])
            _flip_lot_for(obj, obj.disposition)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:returndisposition_detail", pk=pk)

    write_audit_log(request.user, obj, "update", {
        "action": "post", "disposition": obj.disposition, "quantity": str(obj.quantity),
        "move": posted_move.pk if posted_move else None,
        "unit_cost": str(obj.restock_unit_cost)})
    if obj.stock_posted:
        messages.success(
            request,
            f"Posted +{obj.quantity} {obj.return_line.item.sku} into "
            f"{obj.restock_location.code} at {obj.restock_unit_cost} against "
            f"{obj.return_line.return_authorization.number}.")
        messages.info(request, "The unit re-entered stock at its GRADED cost, not at what the "
                               "customer paid. For a FIFO/LIFO item the valuation report and the "
                               "quick on-hand × average-cost figure will now differ — that is "
                               "expected, not a bug.")
    else:
        messages.success(
            request,
            f"Posted −{obj.quantity} {obj.return_line.item.sku} out of "
            f"{obj.restock_location.code} against "
            f"{obj.return_line.return_authorization.number}.")
    return redirect("scm:returndisposition_detail", pk=pk)


@tenant_admin_required
@require_POST
def returndisposition_split(request, pk):
    """Split a bench row in two — the 2-restock / 1-scrap case, made possible.

    Permitted ONLY while ``disposition="received_pending"`` and ``stock_posted`` is False, both
    re-checked inside the lock. This is the one thing that makes disposition-as-a-row survive the
    real receive-then-grade sequence; without it the row grain buys nothing.
    """
    get_object_or_404(ReturnDisposition.objects.only("pk"), pk=pk, tenant=request.tenant)
    row = get_object_or_404(ReturnDisposition, pk=pk, tenant=request.tenant)
    form = ReturnDispositionSplitForm(request.POST, row=row)
    if not form.is_valid():
        messages.error(request, "; ".join(" ".join(errors) for errors in form.errors.values()))
        return redirect("scm:returndisposition_detail", pk=pk)
    quantity = q4(form.cleaned_data["quantity"])
    with transaction.atomic():
        obj = get_object_or_404(ReturnDisposition.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if not obj.is_splittable:
            messages.error(request, "Only an undecided, unposted row can be split — this one has "
                                    "already been graded or posted.")
            return redirect("scm:returndisposition_detail", pk=pk)
        if quantity >= (obj.quantity or ZERO):
            messages.error(request, "Splitting off that much would leave nothing behind — re-grade "
                                    "the row instead.")
            return redirect("scm:returndisposition_detail", pk=pk)
        sibling = ReturnDisposition.objects.create(
            tenant=request.tenant, return_line_id=obj.return_line_id, quantity=quantity,
            received_on=obj.received_on, received_by=obj.received_by, location=obj.location,
            lot_serial_id=obj.lot_serial_id, condition_grade=obj.condition_grade,
            disposition="received_pending", restock_unit_cost=obj.restock_unit_cost,
            notes=f"Split from a row of {obj.quantity}.")
        obj.quantity = q4((obj.quantity or ZERO) - quantity)
        obj.save(update_fields=["quantity", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    {"action": "split", "moved": str(quantity), "sibling": sibling.pk})
    messages.success(request, f"Split {quantity} onto a new bench row — grade each of them "
                              "separately.")
    return redirect("scm:returndisposition_detail", pk=sibling.pk)


@login_required
@require_POST
def returndisposition_mark_refurbished(request, pk):
    """Stamp ``refurbished_on``, which unlocks the restock action on this row.

    ``@login_required``: this records that bench work is finished. It moves no stock — the restock
    that follows is a separate, tenant-admin-gated Post.

    The refurbishment COST is not captured here: repair execution is 4.8's ``WorkOrder``, and the
    grader may revise ``restock_unit_cost`` upward on the row before posting it.
    """
    with transaction.atomic():
        obj = get_object_or_404(ReturnDisposition.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.disposition != "refurbish":
            messages.error(request, "Only a row dispositioned for refurbishment can be marked "
                                    "refurbished.")
            return redirect("scm:returndisposition_detail", pk=pk)
        if obj.refurbished_on is not None:
            messages.info(request, f"This row was already marked refurbished on "
                                   f"{obj.refurbished_on:%d %b %Y}.")
            return redirect("scm:returndisposition_detail", pk=pk)
        obj.refurbished_on = timezone.localdate()
        obj.save(update_fields=["refurbished_on", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "mark_refurbished"})
    messages.success(request, "Marked refurbished — set the restock location and cost, then Post "
                              "it back into sellable stock.")
    return redirect("scm:returndisposition_detail", pk=pk)
