"""SCM 4.9 Quality Management — NonConformance views, including 4.9's ONLY stock posting.

``nonconformance_disposition`` is the one action in the whole sub-module that writes to the
append-only ledger, and it does so exactly once, for exactly one disposition:

* ``scrap`` on stock that is actually somewhere → ONE negative ``adjustment`` StockMove carrying
  ``reference=NCR-…``. No new move type: ``adjustment`` already means write-off, is already
  excluded from 4.7's demand series and already walks correctly in the FIFO/LIFO/WAC valuation.
* ``scrap`` from a GOODS RECEIPT → nothing, ever. Those units were refused at the dock and never
  entered stock, so a negative move would drive the receiving location negative for stock it never
  held. That is ``NonConformance.posts_stock``, asked rather than remembered.
* ``return_to_vendor`` → the decision only. The RMA document belongs to 4.10 Returns Management;
  recording an intent here and a shipment there would be two half-owners of one process.
* everything else → the decision only.

Quarantine posts NOTHING and flips ``LotSerial.status`` instead — see ``_flip_lot_status``.
"""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import (_acting_party, _date_window, _insufficient_stock, _item_qs,
                                     _need_tenant, _post_stock_move, _supplier_parties)
from apps.scm.forms._common import _employee_parties
# The clamped quantizer every computed Decimal in the app goes through — a raw POSTed Decimal
# could exceed what DecimalField(14, 4) holds and fail the whole atomic block on save.
from apps.scm.models._base import q4
from apps.scm.models import CapaAction, LotSerial, NonConformance, StockMove
from apps.scm.forms import NonConformanceDispositionForm, NonConformanceForm

ZERO = Decimal("0")


@login_required
def nonconformance_list(request):
    qs = (NonConformance.objects.filter(tenant=request.tenant)
          .select_related("item", "lot_serial__item", "location", "supplier", "owner",
                          "inspection", "audit"))
    qs = _date_window(qs, request.GET, "detected_on")
    if request.GET.get("overdue", "").strip() == "yes":
        qs = qs.filter(due_date__lt=timezone.localdate()).exclude(
            status__in=("closed", "cancelled"))
    stats = NonConformance.objects.filter(tenant=request.tenant).aggregate(
        open=Count("id", filter=Q(status__in=("open", "investigating"))),
        overdue=Count("id", filter=Q(due_date__lt=timezone.localdate())
                      & ~Q(status__in=("closed", "cancelled"))),
        critical_open=Count("id", filter=Q(severity="critical")
                            & ~Q(status__in=("closed", "cancelled"))),
        dispositioned=Count("id", filter=Q(status="dispositioned")),
        cost_of_quality=Sum("cost_of_quality"),
    )
    return crud_list(
        request, qs, "scm/quality/nonconformance/list.html",
        search_fields=["number", "title", "description", "notes", "item__sku", "item__name",
                       "lot_serial__number"],
        filters=[("status", "status", False), ("severity", "severity", False),
                 ("source", "source", False), ("defect_category", "defect_category", False),
                 ("disposition", "disposition", False), ("item", "item_id", True),
                 ("supplier", "supplier_id", True), ("owner", "owner_id", True)],
        extra_context={
            "status_choices": NonConformance.STATUS_CHOICES,
            "severity_choices": NonConformance.SEVERITY_CHOICES,
            "source_choices": NonConformance.SOURCE_CHOICES,
            "category_choices": NonConformance.DEFECT_CATEGORY_CHOICES,
            "disposition_choices": NonConformance.DISPOSITION_CHOICES,
            "items": _item_qs(request.tenant),
            "suppliers": _supplier_parties(request.tenant),
            "owners": _employee_parties(request.tenant),
            "stats": stats,
        },
    )


@login_required
def nonconformance_create(request):
    if _need_tenant(request):
        return redirect("scm:nonconformance_list")
    return crud_create(request, form_class=NonConformanceForm,
                       template="scm/quality/nonconformance/form.html",
                       success_url="scm:nonconformance_list")


@login_required
def nonconformance_edit(request, pk):
    obj = get_object_or_404(NonConformance, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} and can no "
                                "longer be edited.")
        return redirect("scm:nonconformance_detail", pk=pk)
    return crud_edit(request, model=NonConformance, pk=pk, form_class=NonConformanceForm,
                     template="scm/quality/nonconformance/form.html",
                     success_url="scm:nonconformance_list")


@login_required
def nonconformance_detail(request, pk):
    obj = get_object_or_404(
        NonConformance.objects.select_related("item", "uom", "lot_serial__item", "location",
                                              "supplier", "owner", "detected_by",
                                              "disposition_by", "inspection", "audit",
                                              "goods_receipt", "work_order__item", "shipment"),
        pk=pk, tenant=request.tenant)
    return render(request, "scm/quality/nonconformance/detail.html", {
        "obj": obj,
        # The ledger rows THIS document wrote — reference is the only link StockMove keeps to its
        # source document, exactly as the transfer and work-order detail pages do it.
        "moves": (StockMove.objects.filter(tenant=request.tenant, reference=obj.number)
                  .select_related("item", "location", "lot_serial")[:50]),
        # And where the affected batch has been generally — evidence for a recall decision, which
        # is itself a later pass (4.10 / 12.18).
        "lot_history": obj.lot_history(),
        "capa_actions": obj.capa_actions.select_related("owner", "supplier").all(),
        "disposition_form": NonConformanceDispositionForm(
            initial={"disposition_quantity": obj.quantity_affected}),
    })


@login_required
@require_POST
def nonconformance_delete(request, pk):
    obj = get_object_or_404(NonConformance, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only an open or investigating report can be deleted — cancel it "
                                "instead so its history survives.")
        return redirect("scm:nonconformance_detail", pk=pk)
    if obj.disposition != "pending":
        messages.error(request, "A disposition has been recorded against this report — stock may "
                                "have moved, so it cannot be deleted.")
        return redirect("scm:nonconformance_detail", pk=pk)
    if obj.capa_actions.exists():
        messages.error(request, "This report has corrective actions raised from it and cannot be "
                                "deleted — cancel it instead.")
        return redirect("scm:nonconformance_detail", pk=pk)
    return crud_delete(request, model=NonConformance, pk=pk,
                       success_url="scm:nonconformance_list")


# ============================================================= lifecycle (no stock effect)
def _transition(request, pk, *, from_statuses, to_status, verb, stamp=None):
    """Shared status move — lock, re-read INSIDE the transaction, guard, stamp, audit, redirect."""
    with transaction.atomic():
        obj = get_object_or_404(NonConformance.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status not in from_statuses:
            messages.error(request, f"{obj.number} can't be {verb} from "
                                    f"{obj.get_status_display().lower()}.")
            return redirect("scm:nonconformance_detail", pk=pk)
        fields = ["status", "updated_at"]
        obj.status = to_status
        for field, value in (stamp or {}).items():
            setattr(obj, field, value)
            fields.append(field)
        obj.save(update_fields=list(dict.fromkeys(fields)))
    write_audit_log(request.user, obj, "update", {"action": verb, "status": to_status})
    messages.success(request, f"{obj.number} {verb}.")
    return redirect("scm:nonconformance_detail", pk=pk)


@login_required
@require_POST
def nonconformance_investigate(request, pk):
    return _transition(request, pk, from_statuses=("open",), to_status="investigating",
                       verb="moved to investigating")


@login_required
@require_POST
def nonconformance_close(request, pk):
    """Close the report — refused while the disposition is still pending.

    Closing over a pending disposition would leave affected stock in limbo with a document saying
    the matter is settled.
    """
    obj = get_object_or_404(NonConformance, pk=pk, tenant=request.tenant)
    if obj.status == "dispositioned" and obj.disposition == "pending":
        messages.error(request, "Record a disposition before closing — the affected stock has no "
                                "decision against it.")
        return redirect("scm:nonconformance_detail", pk=pk)
    return _transition(request, pk, from_statuses=("dispositioned",), to_status="closed",
                       verb="closed", stamp={"closed_on": timezone.now()})


@login_required
@require_POST
def nonconformance_cancel(request, pk):
    return _transition(request, pk, from_statuses=("open", "investigating"),
                       to_status="cancelled", verb="cancelled")


# ============================================================= lot status (posts NOTHING)
def _flip_lot_status(request, pk, *, to_status, require_status, verb):
    """Quarantine or release the affected lot. Ruling (b): NO StockMove is posted.

    The goods have not moved — quarantine is a STATUS on the lot, and on-hand is always
    ``Sum(quantity)`` over the ledger, so a stored "blocked quantity" would be a second source of
    truth. Physical segregation, where a tenant wants it, is an ordinary 4.3 StockTransfer into a
    QC-hold location: no new schema, no new location type.

    The lock is on the LOT, not the report: two reports quarantining the same batch at once is the
    race that matters.
    """
    with transaction.atomic():
        obj = get_object_or_404(NonConformance.objects.select_related("lot_serial"),
                                pk=pk, tenant=request.tenant)
        if obj.lot_serial_id is None:
            messages.error(request, "This report names no lot or serial, so there is nothing to "
                                    "quarantine or release.")
            return redirect("scm:nonconformance_detail", pk=pk)
        lot = (LotSerial.objects.select_for_update()
               .filter(pk=obj.lot_serial_id, tenant=request.tenant).first())
        if lot is None:
            messages.error(request, "The lot on this report no longer exists.")
            return redirect("scm:nonconformance_detail", pk=pk)
        if lot.status != require_status:
            messages.error(request, f"Lot {lot.number} is {lot.get_status_display().lower()} — it "
                                    f"cannot be {verb}.")
            return redirect("scm:nonconformance_detail", pk=pk)
        lot.status = to_status
        lot.save(update_fields=["status", "updated_at"])
        obj.quarantine_applied = (to_status == "quarantine")
        obj.save(update_fields=["quarantine_applied", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    {"action": verb, "lot": lot.number, "lot_status": to_status})
    messages.success(request, f"Lot {lot.number} {verb}. No stock movement was posted — the goods "
                              "have not moved.")
    return redirect("scm:nonconformance_detail", pk=pk)


@tenant_admin_required
@require_POST
def nonconformance_quarantine(request, pk):
    return _flip_lot_status(request, pk, to_status="quarantine", require_status="available",
                            verb="quarantined")


@tenant_admin_required
@require_POST
def nonconformance_release_lot(request, pk):
    return _flip_lot_status(request, pk, to_status="available", require_status="quarantine",
                            verb="released")


# ============================================================= the MRB decision (this can post)
@tenant_admin_required
@require_POST
def nonconformance_disposition(request, pk):
    """Record the Material Review Board decision — and post the scrap, when there is one to post.

    The decision fields and the StockMove are written in the SAME ``transaction.atomic()`` from the
    SAME number, so ``disposition_quantity`` and the quantity that left stock cannot disagree. The
    shortfall guard turns "you cannot scrap what you do not have" into a message rather than a
    negative ledger, and the status re-read inside the lock makes a double POST idempotent.
    """
    form = NonConformanceDispositionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "; ".join(
            " ".join(errors) for errors in form.errors.values()))
        return redirect("scm:nonconformance_detail", pk=pk)
    disposition = form.cleaned_data["disposition"]
    quantity = q4(form.cleaned_data.get("disposition_quantity") or ZERO)
    notes = (form.cleaned_data.get("disposition_notes") or "").strip()
    posted = False
    try:
        with transaction.atomic():
            obj = get_object_or_404(
                NonConformance.objects.select_for_update().select_related("item", "location",
                                                                          "lot_serial"),
                pk=pk, tenant=request.tenant)
            if obj.status in ("closed", "cancelled"):
                messages.error(request, f"{obj.number} is "
                                        f"{obj.get_status_display().lower()} — reopen it first.")
                return redirect("scm:nonconformance_detail", pk=pk)
            # Re-read inside the lock: a double-submitted POST must not scrap the same units twice
            # into an append-only ledger where it can never be corrected in place.
            if obj.disposition != "pending":
                messages.info(request, f"{obj.number} was already dispositioned as "
                                       f"{obj.get_disposition_display().lower()}.")
                return redirect("scm:nonconformance_detail", pk=pk)
            if quantity > (obj.quantity_affected or ZERO):
                messages.error(request, f"That dispositions {quantity} against only "
                                        f"{obj.quantity_affected} affected on {obj.number}.")
                return redirect("scm:nonconformance_detail", pk=pk)

            obj.disposition = disposition
            obj.disposition_quantity = quantity
            # accounts.User.party is the app's only User↔Party link; when the login is not tied to
            # a party this stays NULL and the AuditLog row below is the record of who clicked.
            obj.disposition_by = _acting_party(request)
            obj.disposition_on = timezone.now()
            obj.disposition_notes = notes
            obj.status = "dispositioned"

            if obj.posts_stock and quantity > ZERO:
                shortfall = _insufficient_stock(obj.item, obj.location, quantity, obj.lot_serial)
                if shortfall:
                    raise ValidationError(shortfall)
                _post_stock_move(
                    obj.tenant, item=obj.item, location=obj.location, quantity=-quantity,
                    move_type="adjustment", unit_cost=obj.item.average_cost or ZERO,
                    lot_serial=obj.lot_serial, reference=obj.number,
                    reason=f"NCR scrap — {obj.get_defect_category_display()}")
                posted = True
            obj.save(update_fields=["disposition", "disposition_quantity", "disposition_by",
                                    "disposition_on", "disposition_notes", "status", "updated_at"])
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("scm:nonconformance_detail", pk=pk)

    write_audit_log(request.user, obj, "update", {
        "action": "disposition", "disposition": disposition, "quantity": str(quantity),
        "posted_stock": posted})
    messages.success(request, f"{obj.number} dispositioned as "
                              f"{obj.get_disposition_display().lower()}.")
    if posted:
        messages.info(request, f"Posted an inventory adjustment of −{quantity} "
                               f"{obj.item.sku} at {obj.location.code} against {obj.number}.")
    elif disposition == "scrap" and obj.source == "goods_receipt":
        messages.info(request, "Units rejected at the dock never entered stock, so this "
                               "disposition has no ledger effect.")
    elif disposition == "scrap" and obj.location_id is None:
        messages.info(request, "No location is recorded on this report, so nothing could be "
                               "written off — set one and raise a stock adjustment if the units "
                               "are in inventory.")
    elif disposition == "return_to_vendor":
        messages.info(request, "The decision is recorded. The return authorisation itself is a "
                               "4.10 Returns Management document.")
    return redirect("scm:nonconformance_detail", pk=pk)


@login_required
@require_POST
def nonconformance_raise_capa(request, pk):
    """Propose a corrective action from this report — compute-then-convert, once only.

    ``@login_required``: this creates an OPEN draft document, it does not move stock or sign
    anything off (the ``mrp_create_workorder`` precedent).
    """
    with transaction.atomic():
        obj = get_object_or_404(
            NonConformance.objects.select_for_update().select_related("item", "supplier", "owner"),
            pk=pk, tenant=request.tenant)
        existing = obj.capa_actions.first()
        if existing is not None:
            messages.info(request, f"{existing.number} was already raised from this report.")
            return redirect("scm:capaaction_detail", pk=existing.pk)
        capa = CapaAction(
            tenant=request.tenant, action_type="corrective", source="nonconformance",
            nonconformance=obj, item_id=obj.item_id, supplier_id=obj.supplier_id,
            title=obj.title, problem_statement=obj.description,
            containment_action=obj.containment_action, owner_id=obj.owner_id,
            priority="high" if obj.severity in ("critical", "major") else "normal",
            due_date=obj.due_date,
        )
        capa.save()
    write_audit_log(request.user, capa, "create",
                    {"action": "raise_capa", "nonconformance": obj.number})
    messages.success(request, f"{capa.number} raised from {obj.number} — record the root cause "
                              "before implementing it.")
    return redirect("scm:capaaction_detail", pk=capa.pk)
