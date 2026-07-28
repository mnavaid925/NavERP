"""SCM 4.10 Returns Management — ReturnAuthorization views: authorise, approve, settle.

**Nothing in this file posts a StockMove.** The RMA is a non-posting document; the only ledger
writer in 4.10 is ``ReturnDisposition`` and the only accounting writer is
``returnauthorization_draft_credit_note``, which drafts an ``accounting.Invoice(kind="credit_note",
status="draft")`` and stops. **SCM posts NO JournalEntry (L29).**

What the actions here DO change is state that gates money, so they follow the same discipline as a
posting (§7.9): ``@require_POST``, tenant-scoped ``get_object_or_404`` BEFORE the form is touched
(§7.8), inside ``transaction.atomic()`` behind ``select_for_update()`` with the status re-read
INSIDE the transaction, then narrow ``save(update_fields=…)``, then ``write_audit_log``, then the
message.

``@tenant_admin_required`` is reserved for the writes that commit us to a customer: approve,
reject, draft the credit note, draft the replacement order. Raising a return, editing a draft,
receiving goods onto the bench and cancelling one's own draft are ordinary CSR work.
"""
import datetime
import json

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import (_acting_party, _date_window, _item_qs, _location_qs,
                                     _need_tenant)
from apps.scm.forms._common import _customer_parties
# The clamped quantizers every computed Decimal in the app goes through — a raw POSTed Decimal can
# exceed what DecimalField(14, 2)/(14, 4) holds and fail the whole atomic block on save.
from apps.scm.models._base import q2, q4
from apps.scm.models import (ReturnAuthorization, ReturnDisposition, ReturnLine, ReturnPolicy,
                             SalesOrder, WarrantyClaim, evaluate_return_eligibility, select_policy)
from apps.scm.forms import (ReturnApprovalForm, ReturnAuthorizationForm, ReturnLineFormSet,
                            ReturnReceiveAllForm, ReturnRejectForm)

ZERO = Decimal("0")


def _rma_queryset(tenant):
    """The list/detail base queryset — every FK a row renders, joined once.

    ``policy__item_category`` because the badge shows which category the policy governs, and
    ``return_carrier__party`` because ``Carrier.__str__`` reaches its party (§7.6 applies to
    rendered rows as well as to dropdowns).
    """
    return (ReturnAuthorization.objects.filter(tenant=tenant)
            .select_related("customer", "sales_order", "policy__item_category",
                            "return_carrier__party", "dropoff_location", "currency",
                            "credit_note", "replacement_order", "approved_by"))


@login_required
def returnauthorization_list(request):
    qs = _rma_queryset(request.tenant).annotate(
        # §7.3: every one of these carries `_agg`. `quantity_requested_total`,
        # `quantity_received_total`, `is_fully_received` and `days_open` are all MODEL PROPERTIES —
        # naming an annotation after one silently wins on the row and makes the template render a
        # different number from the detail page.
        line_count_agg=Count("lines", distinct=True),
        quantity_requested_agg=Sum("lines__quantity_requested"),
        has_warranty_claim_agg=Exists(
            WarrantyClaim.objects.filter(return_authorization_id=OuterRef("pk"))),
    # Explicit, and it must stay: annotate() sets a GROUP BY, which unsets QuerySet.ordered and
    # drops Meta.ordering from the SQL — the paginator then warns on every load and page 2 is not
    # guaranteed to follow page 1 (the 4.8 finding, applied at 4.9's capaaction_list too).
    ).order_by("-requested_on", "-id")
    qs = _date_window(qs, request.GET, "requested_on")
    if request.GET.get("overdue", "").strip() == "yes":
        # The SQL half of `is_overdue_shipment` — approved, nothing shipped, and past the grace
        # period. It uses a flat 30 days where the property uses the policy's own window, so the
        # filter is deliberately the WIDER net and the row badge is the precise verdict (§7.5: they
        # must not disagree about anything the user can act on, and the badge is what they act on).
        qs = qs.filter(status__in=("approved", "awaiting_receipt"),
                       customer_shipped_on__isnull=True,
                       approved_on__lt=timezone.localdate() - datetime.timedelta(days=30))
    stats = ReturnAuthorization.objects.filter(tenant=request.tenant).aggregate(
        open=Count("id", filter=Q(status__in=ReturnAuthorization.OPEN_STATUSES)),
        awaiting_approval=Count("id", filter=Q(status="requested")),
        awaiting_receipt=Count("id", filter=Q(status__in=("approved", "awaiting_receipt",
                                                          "partially_received"))),
        credit_only=Count("id", filter=Q(return_type="credit_only")
                          & ~Q(status__in=("rejected", "cancelled"))),
        advance_refunds=Count("id", filter=Q(advance_refund=True)
                              & ~Q(status__in=("rejected", "cancelled"))),
        credited=Count("id", filter=Q(credit_note__isnull=False)),
    )
    return crud_list(
        request, qs, "scm/returns/returnauthorization/list.html",
        search_fields=["number", "notes", "return_tracking_number", "counterparty_rma_number",
                       "customer__name", "sales_order__number", "lines__item__sku"],
        filters=[("status", "status", False), ("return_type", "return_type", False),
                 ("source", "source", False), ("resolution", "resolution", False),
                 ("return_method", "return_method", False), ("customer", "customer_id", True),
                 ("policy", "policy_id", True)],
        extra_context={
            "status_choices": ReturnAuthorization.STATUS_CHOICES,
            "type_choices": ReturnAuthorization.RETURN_TYPE_CHOICES,
            "source_choices": ReturnAuthorization.SOURCE_CHOICES,
            "resolution_choices": ReturnAuthorization.RESOLUTION_CHOICES,
            "method_choices": ReturnAuthorization.RETURN_METHOD_CHOICES,
            "customers": _customer_parties(request.tenant),
            "policies": ReturnPolicy.objects.filter(tenant=request.tenant).order_by("priority",
                                                                                    "name"),
            "stats": stats,
        },
    )


@login_required
def returnauthorization_create(request):
    return _returnauthorization_form(request, instance=None)


@login_required
def returnauthorization_edit(request, pk):
    obj = get_object_or_404(ReturnAuthorization, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} and can no "
                                "longer be edited — it is a promise already made to a customer.")
        return redirect("scm:returnauthorization_detail", pk=pk)
    return _returnauthorization_form(request, instance=obj)


def _returnauthorization_form(request, instance):
    """Header + line formset in ONE transaction.

    ``formset.instance = form.instance`` after ``form.is_valid()`` and BEFORE
    ``formset.is_valid()`` (§7.1, place (a)). ``BaseReturnLineFormSet.clean()``'s over-return cap
    reads ``self.instance.sales_order_id``; on CREATE the formset's own instance is an empty
    ``ReturnAuthorization()`` whose ``sales_order_id`` is None, so without that line the cap finds
    nothing to cap against and passes EVERYTHING — silently, on exactly the path it exists for.
    """
    if instance is None and _need_tenant(request):
        return redirect("scm:returnauthorization_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = ReturnAuthorizationForm(request.POST, instance=instance, tenant=request.tenant)
        formset = ReturnLineFormSet(request.POST, instance=instance,
                                    form_kwargs={"tenant": request.tenant})
        form_ok = form.is_valid()
        if form_ok:
            formset.instance = form.instance   # ← load-bearing; see the docstring
        if form_ok and formset.is_valid():
            with transaction.atomic():
                rma = form.save(commit=False)
                rma.tenant = request.tenant
                if not is_edit:
                    rma.status = "requested" if rma.source == "portal" else "draft"
                    # The currency the credit note will be raised in, taken from the order at
                    # creation. A blind return has none — the field is on the form so a CSR can
                    # correct it, and the draft action refuses outright while it is null.
                    if rma.currency_id is None and rma.sales_order_id:
                        rma.currency_id = rma.sales_order.currency_id
                    if rma.policy_id is None:
                        first_line = next(
                            (f.cleaned_data.get("item") for f in formset.forms
                             if getattr(f, "cleaned_data", None)
                             and not f.cleaned_data.get("DELETE")), None)
                        policy = select_policy(request.tenant, first_line)
                        rma.policy = policy
                rma.save()
                formset.instance = rma
                formset.save()
            write_audit_log(request.user, rma, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"{rma.number} saved.")
            return redirect("scm:returnauthorization_detail", pk=rma.pk)
    else:
        form = ReturnAuthorizationForm(
            instance=instance, tenant=request.tenant,
            initial={} if is_edit else {"requested_on": timezone.localdate()})
        formset = ReturnLineFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "scm/returns/returnauthorization/form.html", {
        "form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def returnauthorization_detail(request, pk):
    obj = get_object_or_404(
        _rma_queryset(request.tenant).prefetch_related(
            Prefetch("lines", queryset=ReturnLine.objects.select_related(
                "item__uom", "reason", "lot_serial__item", "sales_order_line__item", "photo")),
            Prefetch("lines__dispositions", queryset=ReturnDisposition.objects.select_related(
                "location", "restock_location", "lot_serial__item", "decided_by", "received_by",
                "nonconformance")),
        ),
        pk=pk)
    lines = list(obj.lines.all())
    # The live eligibility verdict, recomputed for the CSR — NOT the snapshot. The snapshot is
    # what was decided at approval and is shown next to this so the two can be compared.
    verdict = evaluate_return_eligibility(
        obj.sales_order, lines[0].item if lines else None,
        lines[0].reason if lines else None, obj.policy,
        line_value=sum((q2((line.quantity_requested or ZERO) * (line.unit_price or ZERO))
                        for line in lines), ZERO))
    subtotal, fee, tax, total = obj.settlement_figures
    return render(request, "scm/returns/returnauthorization/detail.html", {
        "obj": obj,
        "lines": lines,
        "verdict": verdict,
        "snapshot": obj.snapshot,
        "settlement": {"subtotal": subtotal, "fee": fee, "tax": tax, "total": total},
        "warranty_claims": obj.warranty_claims.select_related("supplier", "item").all(),
        "approval_form": ReturnApprovalForm(initial={
            "resolution": obj.resolution if obj.resolution != "none" else "refund",
            "refund_method": obj.refund_method,
            # `auto_approve` PRE-FILLS this form and never acts. An RMA that approves itself is an
            # RMA nobody looked at, and every approval stamps who did it.
            "approved_on": timezone.localdate() if (obj.policy_id and obj.policy.auto_approve)
            else None,
        }),
        "reject_form": ReturnRejectForm(),
        "receive_form": ReturnReceiveAllForm(tenant=request.tenant),
        "locations": _location_qs(request.tenant),
        "items": _item_qs(request.tenant),
    })


@login_required
@require_POST
def returnauthorization_delete(request, pk):
    obj = get_object_or_404(ReturnAuthorization, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a draft or requested return can be deleted — cancel it "
                                "instead so its history survives.")
        return redirect("scm:returnauthorization_detail", pk=pk)
    if ReturnDisposition.objects.filter(return_line__return_authorization=obj).exists():
        messages.error(request, "Goods have already been received against this return — cancel it "
                                "instead of deleting it.")
        return redirect("scm:returnauthorization_detail", pk=pk)
    if obj.credit_note_id is not None:
        messages.error(request, f"Credit note {obj.credit_note.number} has been drafted against "
                                "this return and cannot be deleted here.")
        return redirect("scm:returnauthorization_detail", pk=pk)
    return crud_delete(request, model=ReturnAuthorization, pk=pk,
                       success_url="scm:returnauthorization_list")


# ============================================================= lifecycle (no stock, no journal)
@tenant_admin_required
@require_POST
def returnauthorization_approve(request, pk):
    """Authorise the return, freeze the eligibility verdict and record the resolution.

    Tenant-admin gated: an approval commits us to giving a customer money back.

    Three things happen in one transaction so they cannot disagree: the verdict is EVALUATED and
    written to ``policy_snapshot`` (editing the policy next month cannot rewrite this decision), the
    resolution is checked against what that verdict allows, and the status moves. The window
    override is recorded IN the frozen verdict, so a later reader sees both what the policy said and
    that a human overruled it.
    """
    # §7.8 — resolve the object, and therefore the TENANT, before touching the form. Form-first, a
    # POST carrying a foreign pk and an invalid payload short-circuits to a redirect without the
    # tenant check ever running.
    get_object_or_404(ReturnAuthorization.objects.only("pk"), pk=pk, tenant=request.tenant)
    form = ReturnApprovalForm(request.POST)
    if not form.is_valid():
        messages.error(request, "; ".join(" ".join(errors) for errors in form.errors.values()))
        return redirect("scm:returnauthorization_detail", pk=pk)
    resolution = form.cleaned_data["resolution"]
    refund_method = form.cleaned_data.get("refund_method") or "none"
    approved_on = form.cleaned_data.get("approved_on") or timezone.localdate()
    override = bool(form.cleaned_data.get("override_window"))
    note = (form.cleaned_data.get("notes") or "").strip()

    with transaction.atomic():
        obj = get_object_or_404(
            ReturnAuthorization.objects.select_for_update()
            .select_related("policy", "sales_order", "customer"),
            pk=pk, tenant=request.tenant)
        # Re-read INSIDE the lock: a double-submitted POST must not re-approve, re-stamp the
        # approver or re-freeze the verdict with a different override flag.
        if obj.status not in ("draft", "requested"):
            messages.info(request, f"{obj.number} is already "
                                   f"{obj.get_status_display().lower()}.")
            return redirect("scm:returnauthorization_detail", pk=pk)
        lines = list(obj.lines.select_related("item", "reason"))
        if not lines:
            messages.error(request, "This return has no lines — there is nothing to authorise.")
            return redirect("scm:returnauthorization_detail", pk=pk)
        # ReturnReason.requires_photo, made satisfiable and then enforced. The portal cannot attach
        # one (customer upload is deferred), so the gate lands here, where a CSR can act on it.
        missing_photo = [line for line in lines
                         if line.reason_id and line.reason.requires_photo and line.photo_id is None]
        if missing_photo:
            messages.error(
                request,
                "A photo is required on " + ", ".join(
                    f"{line.item.sku} ({line.reason.code})" for line in missing_photo)
                + " — attach it to the line before approving.")
            return redirect("scm:returnauthorization_detail", pk=pk)

        line_value = sum((q2((line.quantity_requested or ZERO) * (line.unit_price or ZERO))
                          for line in lines), ZERO)
        verdict = evaluate_return_eligibility(
            obj.sales_order, lines[0].item, lines[0].reason, obj.policy,
            as_of=approved_on, line_value=line_value)
        blocking = [b for b in verdict["blockers"] if "window" in b.lower() or "date" in b.lower()]
        hard = [b for b in verdict["blockers"] if b not in blocking]
        if hard:
            for blocker in hard:
                messages.error(request, blocker)
            return redirect("scm:returnauthorization_detail", pk=pk)
        if blocking and not override:
            for blocker in blocking:
                messages.error(request, blocker)
            messages.info(request, "Tick 'approve anyway' if you are overruling the policy — the "
                                   "override is recorded on the return.")
            return redirect("scm:returnauthorization_detail", pk=pk)
        if resolution not in verdict["allowed_resolutions"] and not override:
            messages.error(
                request,
                f"The policy and the reason allow "
                f"{', '.join(verdict['allowed_resolutions']) or 'nothing'} — not "
                f"{resolution.replace('_', ' ')}.")
            return redirect("scm:returnauthorization_detail", pk=pk)

        verdict["approved_resolution"] = resolution
        verdict["window_overridden"] = bool(blocking and override)
        verdict["approved_by_user"] = request.user.get_username()
        verdict["approved_on"] = approved_on.isoformat()

        # quantity_approved defaults to what was asked for — a partial approval is an edit to the
        # lines, which is a separate, visible act rather than something buried in this payload.
        for line in lines:
            if (line.quantity_approved or ZERO) <= ZERO:
                line.quantity_approved = line.quantity_requested
                line.save(update_fields=["quantity_approved"])

        obj.status = "settled" if obj.return_type == "credit_only" else "awaiting_receipt"
        obj.resolution = resolution
        obj.refund_method = refund_method
        obj.approved_on = approved_on
        obj.approved_by = _acting_party(request)
        obj.policy_snapshot = json.dumps(verdict)
        fields = ["status", "resolution", "refund_method", "approved_on", "approved_by",
                  "policy_snapshot", "updated_at"]
        if note:
            obj.notes = f"{obj.notes}\n[{approved_on:%Y-%m-%d} approved] {note}".strip()
            fields.append("notes")
        obj.save(update_fields=fields)

    write_audit_log(request.user, obj, "update", {
        "action": "approve", "resolution": resolution, "status": obj.status,
        "window_overridden": verdict["window_overridden"]})
    messages.success(request, f"{obj.number} approved for "
                              f"{obj.get_resolution_display().lower()}.")
    if obj.return_type == "credit_only":
        messages.info(request, "This is a credit-only return — nothing is coming back, so it goes "
                               "straight to the refund queue.")
    else:
        messages.info(request, "Print the return slip for the customer, then receive the goods "
                               "onto the returns bench when they arrive.")
    return redirect("scm:returnauthorization_detail", pk=pk)


@tenant_admin_required
@require_POST
def returnauthorization_reject(request, pk):
    """Refuse the return. A reason is required and is recorded on the RMA the customer can see."""
    get_object_or_404(ReturnAuthorization.objects.only("pk"), pk=pk, tenant=request.tenant)
    form = ReturnRejectForm(request.POST)
    if not form.is_valid():
        messages.error(request, "; ".join(" ".join(errors) for errors in form.errors.values()))
        return redirect("scm:returnauthorization_detail", pk=pk)
    reason = form.cleaned_data["rejected_reason"].strip()
    with transaction.atomic():
        obj = get_object_or_404(ReturnAuthorization.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status not in ("draft", "requested"):
            messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} — it can "
                                    "no longer be rejected.")
            return redirect("scm:returnauthorization_detail", pk=pk)
        obj.status = "rejected"
        obj.rejected_reason = reason[:255]
        obj.save(update_fields=["status", "rejected_reason", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "reject", "reason": reason[:200]})
    messages.success(request, f"{obj.number} rejected.")
    return redirect("scm:returnauthorization_detail", pk=pk)


@login_required
@require_POST
def returnauthorization_cancel(request, pk):
    """Withdraw the return. Refused once goods are physically on the bench.

    ``@login_required``, not tenant-admin: cancelling a return nobody has acted on is ordinary CSR
    work. The moment stock is involved the guard below stops it regardless of who is asking.
    """
    with transaction.atomic():
        obj = get_object_or_404(ReturnAuthorization.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.is_terminal:
            messages.info(request, f"{obj.number} is already "
                                   f"{obj.get_status_display().lower()}.")
            return redirect("scm:returnauthorization_detail", pk=pk)
        if ReturnDisposition.objects.filter(return_line__return_authorization=obj).exists():
            messages.error(request, "Goods have already been received against this return — "
                                    "disposition them rather than cancelling the paperwork they "
                                    "arrived on.")
            return redirect("scm:returnauthorization_detail", pk=pk)
        if obj.credit_note_id is not None:
            messages.error(request, f"Credit note {obj.credit_note.number} has been drafted "
                                    "against this return — void it in Accounts Receivable first.")
            return redirect("scm:returnauthorization_detail", pk=pk)
        obj.status = "cancelled"
        obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "cancel"})
    messages.success(request, f"{obj.number} cancelled.")
    return redirect("scm:returnauthorization_detail", pk=pk)


@login_required
@require_POST
def returnauthorization_receive_all(request, pk):
    """One click: a ``received_pending`` bench row per approved line.

    **Posts NOTHING.** Intake records quantity, grade, date and bench location as DATA — see the
    ``ReturnDisposition`` module docstring for why the bench is deliberately off-ledger (there is no
    blocked-stock location type, and ``Item.on_hand()`` sums every location, so an intake receipt
    would inflate on-hand, valuation and 4.7's reorder inputs tenant-wide).

    Promoted from mitigation to scope: without it the flow is unpleasant enough to sink the demo.
    """
    get_object_or_404(ReturnAuthorization.objects.only("pk"), pk=pk, tenant=request.tenant)
    form = ReturnReceiveAllForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        messages.error(request, "; ".join(" ".join(errors) for errors in form.errors.values()))
        return redirect("scm:returnauthorization_detail", pk=pk)
    location = form.cleaned_data["location"]
    grade = form.cleaned_data["condition_grade"]
    received_on = form.cleaned_data.get("received_on") or timezone.localdate()
    party = _acting_party(request)

    created, skipped = 0, []
    with transaction.atomic():
        obj = get_object_or_404(
            ReturnAuthorization.objects.select_for_update().select_related("policy"),
            pk=pk, tenant=request.tenant)
        if obj.return_type == "credit_only":
            messages.error(request, "A credit-only return has nothing coming back — settle it from "
                                    "the refund queue instead.")
            return redirect("scm:returnauthorization_detail", pk=pk)
        if obj.status not in ("approved", "awaiting_receipt", "partially_received"):
            messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} — approve "
                                    "it before receiving anything against it.")
            return redirect("scm:returnauthorization_detail", pk=pk)
        policy = obj.policy or select_policy(request.tenant)
        for line in obj.lines.select_related("item", "reason", "lot_serial"):
            outstanding = q4(line.quantity_outstanding)
            if outstanding <= ZERO:
                continue
            # A tracked item needs its lot, and only the LINE knows which one came back. Rather
            # than write an untraceable ledger candidate, skip it and say so — the row can be added
            # by hand on the bench with the lot filled in.
            if line.item_id and line.item.tracking != "none" and line.lot_serial_id is None:
                skipped.append(f"{line.item.sku} (no lot/serial recorded on the line)")
                continue
            ReturnDisposition.objects.create(
                tenant=request.tenant, return_line=line, quantity=outstanding,
                received_on=received_on, received_by=party, location=location,
                lot_serial_id=line.lot_serial_id, condition_grade=grade,
                disposition="received_pending",
                restock_unit_cost=(policy.restock_cost_for(
                    grade, line.item.average_cost if line.item_id else ZERO)
                    if policy is not None else q4(line.unit_cost or ZERO)),
                notes=f"Received against {obj.number}.")
            created += 1
        if created:
            obj.status = "received" if obj.is_fully_received else "partially_received"
            obj.save(update_fields=["status", "updated_at"])

    if not created:
        messages.info(request, "Nothing was outstanding on this return — every approved line is "
                               "already on the bench.")
        for note in skipped:
            messages.error(request, f"Skipped {note}.")
        return redirect("scm:returnauthorization_detail", pk=pk)
    write_audit_log(request.user, obj, "update",
                    {"action": "receive_all", "rows": created, "location": location.code})
    messages.success(request, f"{created} row(s) received onto {location.code} against "
                              f"{obj.number} — grade and disposition them on the bench.")
    messages.info(request, "Nothing was posted to the stock ledger: goods on the returns bench are "
                           "deliberately off-ledger until they are dispositioned.")
    for note in skipped:
        messages.error(request, f"Skipped {note}.")
    return redirect("scm:returnauthorization_detail", pk=pk)


# ============================================================= the accounting hand-off (L29)
@tenant_admin_required
@require_POST
def returnauthorization_draft_credit_note(request, pk):
    """Draft an ``accounting.Invoice(kind="credit_note", status="draft")`` and STOP.

    A verbatim clone of ``freightinvoice_handoff`` and ``crm.dealinvoice_from_quote``: SCM drafts,
    Accounting issues. **No JournalEntry, ever (L29).** ``invoice_post`` is Accounting's action;
    ``accounting.Payment(direction="out")`` is not created either — it posts Dr AP-liability / Cr
    Bank, which is the wrong account for a customer refund, and ``Payment.bank_account`` is a
    non-null PROTECT FK SCM has no business choosing.

    **The negative-fee guard.** The restocking fee is netted INSIDE the credit as a negative
    ``InvoiceLine`` — legal, ``InvoiceLine`` has no ``MinValueValidator``. But ``invoice_post``
    guards ``if ar and income and inv.total > ZERO`` and ``recompute_payment_status`` only reaches
    ``paid`` when ``total > ZERO``, so a credit note whose fees meet or exceed its value is a
    PERMANENTLY unpostable, unpayable document. The total is therefore computed FIRST and the draft
    is refused when it is not positive.

    **``tax_pct`` is carried across.** ``Invoice.recalc_totals()`` computes tax as
    ``line_total × tax_rate_pct / 100``, so carrying the snapshotted rate is all that is required —
    and forgetting it under-credits every customer by the VAT, silently.

    **Known Module 2 defect, flagged not compensated:** ``invoice_post`` does not branch on
    ``kind``, so an ISSUED credit note posts Dr AR / Cr Income (backwards) and while ``sent`` it
    ADDS to the open exposure ``_evaluate_hold`` reads. 4.10 must not touch the ledger to work
    around that.
    """
    get_object_or_404(ReturnAuthorization.objects.only("pk"), pk=pk, tenant=request.tenant)
    with transaction.atomic():
        obj = get_object_or_404(
            ReturnAuthorization.objects.select_for_update()
            .select_related("customer", "currency", "credit_note"),
            pk=pk, tenant=request.tenant)
        # Idempotence, re-read inside the lock: a double POST must not raise two credit notes.
        if obj.credit_note_id is not None:
            messages.info(request, f"Credit note {obj.credit_note.number} has already been drafted "
                                   f"for {obj.number}.")
            return redirect("scm:returnauthorization_detail", pk=pk)
        if obj.status in ("draft", "requested", "rejected", "cancelled"):
            messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} — approve "
                                    "it before crediting anything.")
            return redirect("scm:returnauthorization_detail", pk=pk)
        if not obj.is_settleable:
            messages.error(request, "There is nothing credit-bearing on this return yet — receive "
                                    "and disposition the goods first.")
            return redirect("scm:returnauthorization_detail", pk=pk)
        if obj.currency_id is None:
            messages.error(request, "This return has no currency, so a credit note cannot be "
                                    "raised — set one on the return first.")
            return redirect("scm:returnauthorization_detail", pk=pk)
        subtotal, fee, tax, total = obj.settlement_figures
        if total <= ZERO:
            messages.error(
                request,
                f"The fees on this return ({fee}) meet or exceed its value ({subtotal}), so the "
                f"credit note would total {total} and could never be posted or paid. Raise the "
                "fee as a separate charge in Accounting instead.")
            return redirect("scm:returnauthorization_detail", pk=pk)

        # Local import inside the function body — the freightinvoice_handoff posture. SCM does not
        # import accounting at module scope.
        from apps.accounting.models import Invoice, InvoiceLine
        invoice = Invoice(tenant=request.tenant, party=obj.customer, kind="credit_note",
                          status="draft", issue_date=timezone.localdate(),
                          currency_id=obj.currency_id,
                          notes=f"Return {obj.number}"
                                + (f" · order {obj.sales_order.number}" if obj.sales_order_id
                                   else ""))
        invoice.save()
        for line in obj.lines.select_related("item", "reason"):
            quantity = line.credit_quantity     # FROM THE DISPOSITION ROWS, never quantity_approved
            if quantity <= ZERO:
                continue
            InvoiceLine.objects.create(
                invoice=invoice,
                description=(f"{line.item.sku} — {line.description or line.item.name}"
                             f" (return {obj.number})"),
                quantity=quantity, unit_price=line.unit_price or ZERO,
                tax_rate_pct=line.tax_pct or ZERO)
        if fee > ZERO:
            InvoiceLine.objects.create(
                invoice=invoice, description=f"Restocking / handling fee — {obj.number}",
                quantity=Decimal("1"), unit_price=-fee, tax_rate_pct=ZERO)
        invoice.recalc_totals()

        obj.credit_note = invoice
        obj.refund_subtotal, obj.fee_total, obj.tax_total, obj.credit_total = (
            subtotal, fee, tax, total)
        if obj.status in ("received", "partially_received"):
            obj.status = "settled"
        obj.save(update_fields=["credit_note", "refund_subtotal", "fee_total", "tax_total",
                                "credit_total", "status", "updated_at"])

    write_audit_log(request.user, obj, "update",
                    {"action": "credit_note", "invoice": invoice.number, "total": str(total)})
    messages.success(request, f"Draft credit note {invoice.number} created for {total}. Issue it "
                              "from Accounts Receivable — SCM posts no journal entry.")
    messages.info(request, "Note for Accounting: invoice_post does not branch on Invoice.kind, so "
                           "an issued credit note currently posts Dr AR / Cr Income. That is a "
                           "Module 2 defect and this module deliberately does not work around it.")
    return redirect("scm:returnauthorization_detail", pk=pk)


@tenant_admin_required
@require_POST
def returnauthorization_draft_replacement(request, pk):
    """Draft the exchange order — a DRAFT ``SalesOrder``, priced at zero, once only.

    Compute-then-convert (the ``mrp_create_workorder`` / ``qualityinspection_raise_ncr`` posture):
    the order lands as a draft with everything the return already knows, and a human owns it from
    there. Tenant-admin gated because it commits us to shipping goods.

    Lines are raised at unit_price 0: the customer already paid for these units on the original
    order, and charging again — or discounting to zero on a line that says otherwise — is a decision
    for whoever prices the exchange, not a default.
    """
    get_object_or_404(ReturnAuthorization.objects.only("pk"), pk=pk, tenant=request.tenant)
    with transaction.atomic():
        obj = get_object_or_404(
            ReturnAuthorization.objects.select_for_update()
            .select_related("customer", "sales_order", "replacement_order"),
            pk=pk, tenant=request.tenant)
        if obj.replacement_order_id is not None:
            messages.info(request, f"{obj.replacement_order.number} was already raised from "
                                   f"{obj.number}.")
            return redirect("scm:salesorder_detail", pk=obj.replacement_order_id)
        if obj.resolution != "exchange":
            messages.error(request, "This return is not resolving as an exchange — change the "
                                    "resolution before raising a replacement order.")
            return redirect("scm:returnauthorization_detail", pk=pk)
        if obj.status in ("draft", "requested", "rejected", "cancelled"):
            messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} — approve "
                                    "it before raising a replacement.")
            return redirect("scm:returnauthorization_detail", pk=pk)
        lines = [line for line in obj.lines.select_related("item")
                 if (line.quantity_approved or line.quantity_requested or ZERO) > ZERO]
        if not lines:
            messages.error(request, "There are no approved lines to replace.")
            return redirect("scm:returnauthorization_detail", pk=pk)

        from apps.scm.models import SalesOrderLine
        order = SalesOrder(
            tenant=request.tenant, customer=obj.customer, source_channel="manual",
            order_date=timezone.localdate(), currency_id=obj.currency_id,
            payment_terms_id=(obj.sales_order.payment_terms_id if obj.sales_order_id else None),
            ship_to_address_id=(obj.sales_order.ship_to_address_id if obj.sales_order_id else None),
            notes=f"Exchange for return {obj.number}.")
        order.save()
        for line in lines:
            SalesOrderLine.objects.create(
                sales_order=order, item=line.item,
                description=line.description or "",
                quantity_ordered=line.quantity_approved or line.quantity_requested,
                unit_price=ZERO, tax_pct=line.tax_pct or ZERO)
        order.recalc_totals()
        obj.replacement_order = order
        obj.save(update_fields=["replacement_order", "updated_at"])

    write_audit_log(request.user, order, "create",
                    {"action": "draft_replacement", "return": obj.number})
    messages.success(request, f"Draft order {order.number} raised as the exchange for "
                              f"{obj.number} — price and submit it from Order Management.")
    return redirect("scm:salesorder_detail", pk=order.pk)


@login_required
@require_POST
def returnauthorization_raise_warranty_claim(request, pk):
    """Propose a supplier warranty claim from this return — compute-then-convert, once only.

    ``@login_required``, not tenant-admin, for the same reason ``nonconformance_raise_capa`` is:
    this creates a DRAFT document, it moves no stock and signs nothing off.

    The supplier is taken from the reason's ``fault_party`` where that says ``supplier`` and the
    item has a known source; where it does not, the claim is still drafted WITHOUT a supplier so a
    human can name one — refusing here would mean the button does nothing on exactly the returns
    somebody wants to chase.
    """
    with transaction.atomic():
        obj = get_object_or_404(
            ReturnAuthorization.objects.select_for_update().select_related("customer", "policy"),
            pk=pk, tenant=request.tenant)
        existing = obj.warranty_claims.first()
        if existing is not None:
            messages.info(request, f"{existing.number} was already raised from {obj.number}.")
            return redirect("scm:warrantyclaim_detail", pk=existing.pk)
        if obj.status in ("draft", "requested", "rejected", "cancelled"):
            messages.error(request, "Approve the return before chasing the supplier for it.")
            return redirect("scm:returnauthorization_detail", pk=pk)
        line = obj.lines.select_related("item", "reason", "lot_serial").first()
        if line is None or line.item_id is None:
            messages.error(request, "This return has no item to claim against.")
            return redirect("scm:returnauthorization_detail", pk=pk)
        supplier = _last_supplier_for(request.tenant, line.item_id)
        if supplier is None:
            messages.error(request, f"No supplier is known for {line.item.sku} — raise the claim "
                                    "from the Warranty Claims page and name one.")
            return redirect("scm:warrantyclaim_create")
        claim = WarrantyClaim(
            tenant=request.tenant, supplier=supplier, item_id=line.item_id,
            quantity_claimed=line.quantity_approved or line.quantity_requested,
            lot_serial_id=line.lot_serial_id, return_authorization=obj,
            purchase_date=(obj.sales_order.order_date if obj.sales_order_id else None),
            failure_date=obj.requested_on,
            defect_classification="unknown",
            usage_context=line.condition_reported or "",
            description=(f"Raised from return {obj.number} for {obj.customer.name}. Customer "
                         f"reason: {line.reason.name if line.reason_id else 'not recorded'}."),
            response_due_on=timezone.localdate() + datetime.timedelta(days=30))
        claim.save()
    write_audit_log(request.user, claim, "create",
                    {"action": "raise_warranty_claim", "return": obj.number})
    messages.success(request, f"{claim.number} drafted against {supplier.name} — add the cost "
                              "lines before submitting it.")
    return redirect("scm:warrantyclaim_detail", pk=claim.pk)


def _last_supplier_for(tenant, item_id):
    """Best-effort: who did we last buy this item from?

    4.1's purchase-order lines are FREE TEXT (``sku_hint``) because they predate the item master,
    so this matches on that hint rather than pretending an FK exists. Returns None when nothing
    matches — the caller says so rather than guessing.
    """
    from apps.scm.models import Item, PurchaseOrderLine
    item = Item.objects.filter(tenant=tenant, pk=item_id).only("sku").first()
    if item is None:
        return None
    line = (PurchaseOrderLine.objects
            .filter(purchase_order__tenant=tenant, sku_hint__iexact=item.sku)
            .select_related("purchase_order__vendor")
            .order_by("-purchase_order__order_date", "-id").first())
    return line.purchase_order.vendor if line is not None else None
