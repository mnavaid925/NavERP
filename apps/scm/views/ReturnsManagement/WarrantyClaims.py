"""SCM 4.10 Returns Management — WarrantyClaim views: the supplier-recovery side.

**Nothing here posts a StockMove and nothing here drafts an accounting document.**
``accounting.Bill`` has NO ``kind`` field — unlike ``accounting.Invoice``, which does and is what
the customer-side credit note uses — so there is no vendor-credit document to draft. This module
RECORDS ``amount_approved`` / ``amount_credited`` / ``credit_reference`` / ``credit_received_on``
and stops. **FLAG TO MODULE 2/6: adding ``Bill.kind`` is the change that would unlock a real vendor
credit here.** SCM posts no JournalEntry either way (L29).

``@tenant_admin_required`` is on the three writes that speak to a counterparty or move money:
submit, record their response, record their credit. Drafting and editing a claim is ordinary work.
"""
import datetime

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _date_window, _item_qs, _need_tenant, _supplier_parties
from apps.scm.models._base import q2
from apps.scm.models import WarrantyClaim
from apps.scm.forms import (WarrantyClaimCostFormSet, WarrantyClaimCreditForm, WarrantyClaimForm,
                            WarrantyClaimResponseForm)

ZERO = Decimal("0")


def _claim_queryset(tenant):
    """Every FK a claim row renders, joined once. ``lot_serial__item`` because
    ``LotSerial.__str__`` reads ``item.sku``; ``return_authorization__customer`` because
    ``ReturnAuthorization.__str__`` reads ``customer.name`` (§7.6)."""
    return (WarrantyClaim.objects.filter(tenant=tenant)
            .select_related("supplier", "item__uom", "lot_serial__item",
                            "return_authorization__customer", "nonconformance", "goods_receipt"))


@login_required
def warrantyclaim_list(request):
    qs = _claim_queryset(request.tenant).annotate(
        # §7.3 — `amount_claimed_total`, `recovery_variance`, `recovery_rate_pct`, `is_overdue`,
        # `days_open` and `is_possible_duplicate` are ALL model properties. Every annotation here
        # carries `_agg` so none of them can shadow one on the row.
        amount_claimed_agg=Sum("costs__amount_claimed"),
        cost_line_count_agg=Count("costs", distinct=True),
    # Explicit: annotate() sets a GROUP BY, which unsets QuerySet.ordered and drops Meta.ordering
    # from the SQL — without this the paginator warns and page 2 need not follow page 1.
    ).order_by("-created_at", "-id")
    qs = _date_window(qs, request.GET, "submitted_on")
    if request.GET.get("overdue", "").strip() == "yes":
        # The SQL half of `is_overdue` — same three conditions the property tests, so the filtered
        # set and the badged set agree (§7.5).
        qs = qs.filter(response_due_on__lt=timezone.localdate(), responded_on__isnull=True) \
               .exclude(status__in=WarrantyClaim.TERMINAL_STATUSES)
    stats = WarrantyClaim.objects.filter(tenant=request.tenant).aggregate(
        open=Count("id", filter=Q(status__in=WarrantyClaim.OPEN_STATUSES)),
        awaiting_response=Count("id", filter=Q(status__in=("submitted", "acknowledged"))),
        overdue=Count("id", filter=Q(response_due_on__lt=timezone.localdate())
                      & Q(responded_on__isnull=True)
                      & ~Q(status__in=WarrantyClaim.TERMINAL_STATUSES)),
        approved_value=Sum("amount_approved"),
        credited_value=Sum("amount_credited"),
    )
    return crud_list(
        request, qs, "scm/returns/warrantyclaim/list.html",
        search_fields=["number", "supplier_rma_number", "serial_reference", "description",
                       "notes", "supplier__name", "item__sku", "item__name",
                       "lot_serial__number"],
        filters=[("status", "status", False),
                 ("defect_classification", "defect_classification", False),
                 ("submission_channel", "submission_channel", False),
                 ("supplier", "supplier_id", True), ("item", "item_id", True)],
        extra_context={
            "status_choices": WarrantyClaim.STATUS_CHOICES,
            "defect_choices": WarrantyClaim.DEFECT_CLASSIFICATION_CHOICES,
            "channel_choices": WarrantyClaim.SUBMISSION_CHANNEL_CHOICES,
            "suppliers": _supplier_parties(request.tenant),
            "items": _item_qs(request.tenant),
            "stats": stats,
        },
    )


@login_required
def warrantyclaim_create(request):
    return _warrantyclaim_form(request, instance=None)


@login_required
def warrantyclaim_edit(request, pk):
    obj = get_object_or_404(WarrantyClaim, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, f"{obj.number} has been {obj.get_status_display().lower()} — its "
                                "cost lines are what the supplier was shown and can no longer be "
                                "edited.")
        return redirect("scm:warrantyclaim_detail", pk=pk)
    return _warrantyclaim_form(request, instance=obj)


def _warrantyclaim_form(request, instance):
    """Header + typed cost formset in ONE transaction.

    ``formset.instance = form.instance`` before ``formset.is_valid()``:
    ``BaseWarrantyClaimCostFormSet.clean()`` reads the PARENT's ``status`` and its row count on
    file (§7.1/§7.2). On create the formset's own instance is an empty ``WarrantyClaim()`` whose
    ``pk`` is None, and without the assignment the locked/row-count guards read the wrong object.
    """
    if instance is None and _need_tenant(request):
        return redirect("scm:warrantyclaim_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = WarrantyClaimForm(request.POST, instance=instance, tenant=request.tenant)
        formset = WarrantyClaimCostFormSet(request.POST, instance=instance,
                                           form_kwargs={"tenant": request.tenant})
        form_ok = form.is_valid()
        if form_ok:
            formset.instance = form.instance   # ← load-bearing; see the docstring
        if form_ok and formset.is_valid():
            with transaction.atomic():
                claim = form.save(commit=False)
                claim.tenant = request.tenant
                claim.save()
                formset.instance = claim
                formset.save()
            write_audit_log(request.user, claim, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"{claim.number} saved.")
            return redirect("scm:warrantyclaim_detail", pk=claim.pk)
    else:
        form = WarrantyClaimForm(instance=instance, tenant=request.tenant,
                                 initial={} if is_edit else {
                                     "failure_date": timezone.localdate(),
                                     "response_due_on": timezone.localdate()
                                     + datetime.timedelta(days=30)})
        formset = WarrantyClaimCostFormSet(instance=instance,
                                           form_kwargs={"tenant": request.tenant})
    return render(request, "scm/returns/warrantyclaim/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def warrantyclaim_detail(request, pk):
    obj = get_object_or_404(_claim_queryset(request.tenant), pk=pk)
    return render(request, "scm/returns/warrantyclaim/detail.html", {
        "obj": obj,
        "costs": obj.costs.all(),
        "amount_claimed_total": obj.amount_claimed_total,
        "cost_approved_total": obj.cost_approved_total,
        "recovery_variance": obj.recovery_variance,
        "recovery_rate_pct": obj.recovery_rate_pct,
        "is_in_warranty": obj.is_in_warranty,
        "is_possible_duplicate": obj.is_possible_duplicate,
        # The read-only ledger panel, copied in shape from NonConformance.lot_history().
        "lot_history": obj.lot_history(),
        "response_form": WarrantyClaimResponseForm(
            initial={"amount_approved": obj.amount_claimed_total}),
        "credit_form": WarrantyClaimCreditForm(
            initial={"amount_credited": obj.amount_approved or ZERO}),
    })


@login_required
@require_POST
def warrantyclaim_delete(request, pk):
    obj = get_object_or_404(WarrantyClaim, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a draft claim can be deleted — a submitted one is a record "
                                "of what the supplier was asked for.")
        return redirect("scm:warrantyclaim_detail", pk=pk)
    return crud_delete(request, model=WarrantyClaim, pk=pk, success_url="scm:warrantyclaim_list")


# ============================================================= the negotiation (no stock, no GL)
@tenant_admin_required
@require_POST
def warrantyclaim_submit(request, pk):
    """Send the claim to the supplier — stamps ``submitted_on`` and locks the cost lines.

    The transport is DEFERRED, deliberately and in the house pattern (``SalesOrder``'s
    ``confirmation_sent_at`` / ``shipped_notification_at``): the fact is recorded, the email/EDI is
    the integration module's job. ``submission_channel`` is the data hook that says which one it
    would have been.
    """
    with transaction.atomic():
        obj = get_object_or_404(WarrantyClaim.objects.select_for_update().select_related("supplier"),
                                pk=pk, tenant=request.tenant)
        # Re-read inside the lock: a double POST must not re-stamp the submission date, which is
        # what the response deadline is measured against.
        if obj.status != "draft":
            messages.info(request, f"{obj.number} is already "
                                   f"{obj.get_status_display().lower()}.")
            return redirect("scm:warrantyclaim_detail", pk=pk)
        if obj.amount_claimed_total <= ZERO:
            messages.error(request, "This claim asks the supplier for nothing — add at least one "
                                    "cost line before submitting it.")
            return redirect("scm:warrantyclaim_detail", pk=pk)
        if not obj.is_in_warranty:
            # Advisory rather than fatal: a goodwill claim outside cover is a real thing suppliers
            # accept, and refusing it here would just push the user into faking a date.
            messages.warning(request, "This unit is outside its warranty window on the dates "
                                      "recorded — submitting it anyway is a goodwill claim.")
        obj.status = "submitted"
        obj.submitted_on = timezone.localdate()
        fields = ["status", "submitted_on", "updated_at"]
        if obj.response_due_on is None:
            obj.response_due_on = obj.submitted_on + datetime.timedelta(days=30)
            fields.append("response_due_on")
        obj.save(update_fields=fields)
    write_audit_log(request.user, obj, "update",
                    {"action": "submit", "channel": obj.submission_channel})
    messages.success(request, f"{obj.number} submitted to {obj.supplier.name} by "
                              f"{obj.get_submission_channel_display().lower()}. Nothing was sent "
                              "automatically — the transport is deferred; this records the fact.")
    return redirect("scm:warrantyclaim_detail", pk=pk)


@tenant_admin_required
@require_POST
def warrantyclaim_record_response(request, pk):
    """Record what the supplier came back with. Their side of the negotiation, not ours.

    ``amount_approved`` is checked against the claim's own total INSIDE the lock: a supplier
    approving more than was asked for is the one answer that is nonsense whatever they said, and
    letting it through would make every recovery-rate figure exceed 100%.
    """
    # §7.8 — tenant first.
    get_object_or_404(WarrantyClaim.objects.only("pk"), pk=pk, tenant=request.tenant)
    form = WarrantyClaimResponseForm(request.POST)
    if not form.is_valid():
        messages.error(request, "; ".join(" ".join(errors) for errors in form.errors.values()))
        return redirect("scm:warrantyclaim_detail", pk=pk)
    outcome = form.cleaned_data["outcome"]
    amount = q2(form.cleaned_data.get("amount_approved") or ZERO)
    responded_on = form.cleaned_data.get("responded_on") or timezone.localdate()
    their_ref = (form.cleaned_data.get("supplier_rma_number") or "").strip()
    note = (form.cleaned_data.get("supplier_response_notes") or "").strip()

    with transaction.atomic():
        obj = get_object_or_404(WarrantyClaim.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status == "draft":
            messages.error(request, "Submit the claim before recording a response to it.")
            return redirect("scm:warrantyclaim_detail", pk=pk)
        # Re-read inside the lock: recording a second response would overwrite the first without
        # trace, and the amounts are what a recovery report is computed from.
        if obj.status in WarrantyClaim.RESPONDED_STATUSES or obj.status in ("credited", "closed"):
            messages.info(request, f"A response has already been recorded on {obj.number} "
                                   f"({obj.get_status_display()}).")
            return redirect("scm:warrantyclaim_detail", pk=pk)
        claimed = obj.amount_claimed_total
        if amount > claimed:
            messages.error(request, f"The supplier cannot approve {amount} against a claim of "
                                    f"{claimed}.")
            return redirect("scm:warrantyclaim_detail", pk=pk)
        obj.status = outcome
        obj.amount_approved = amount
        obj.responded_on = responded_on
        fields = ["status", "amount_approved", "responded_on", "updated_at"]
        if their_ref:
            obj.supplier_rma_number = their_ref[:64]
            fields.append("supplier_rma_number")
        if note:
            stamp = f"[{responded_on:%Y-%m-%d} {obj.get_status_display()}] {note}"
            obj.supplier_response_notes = f"{obj.supplier_response_notes}\n{stamp}".strip()
            fields.append("supplier_response_notes")
        obj.save(update_fields=fields)
    write_audit_log(request.user, obj, "update",
                    {"action": "record_response", "outcome": outcome, "amount": str(amount)})
    messages.success(request, f"{obj.number}: {obj.get_status_display().lower()} at {amount} of "
                              f"{claimed} claimed.")
    if obj.is_possible_duplicate:
        messages.warning(request, "Another live claim on this supplier carries the same reference "
                                  "— check it is not the same failure claimed twice.")
    return redirect("scm:warrantyclaim_detail", pk=pk)


@tenant_admin_required
@require_POST
def warrantyclaim_record_credit(request, pk):
    """Record the credit the supplier actually gave us. **Drafts nothing (see the module docstring).**"""
    get_object_or_404(WarrantyClaim.objects.only("pk"), pk=pk, tenant=request.tenant)
    form = WarrantyClaimCreditForm(request.POST)
    if not form.is_valid():
        messages.error(request, "; ".join(" ".join(errors) for errors in form.errors.values()))
        return redirect("scm:warrantyclaim_detail", pk=pk)
    amount = q2(form.cleaned_data["amount_credited"])
    reference = form.cleaned_data["credit_reference"].strip()
    received_on = form.cleaned_data.get("credit_received_on") or timezone.localdate()

    with transaction.atomic():
        obj = get_object_or_404(WarrantyClaim.objects.select_for_update(),
                                pk=pk, tenant=request.tenant)
        if obj.status not in ("approved", "partially_approved"):
            messages.error(request, "Record the supplier's approval before recording their credit.")
            return redirect("scm:warrantyclaim_detail", pk=pk)
        # Idempotency re-read inside the lock — a double POST must not double the recovery figure.
        if obj.credit_received_on is not None:
            messages.info(request, f"A credit of {obj.amount_credited} was already recorded on "
                                   f"{obj.number} ({obj.credit_reference}).")
            return redirect("scm:warrantyclaim_detail", pk=pk)
        if amount > (obj.amount_approved or ZERO):
            messages.error(request, f"That credits {amount} against an approval of "
                                    f"{obj.amount_approved}.")
            return redirect("scm:warrantyclaim_detail", pk=pk)
        obj.amount_credited = amount
        obj.credit_reference = reference[:64]
        obj.credit_received_on = received_on
        obj.status = "credited"
        obj.save(update_fields=["amount_credited", "credit_reference", "credit_received_on",
                                "status", "updated_at"])
    write_audit_log(request.user, obj, "update",
                    {"action": "record_credit", "amount": str(amount), "reference": reference[:60]})
    messages.success(request, f"{obj.number} credited {amount} (their reference {reference}). "
                              f"Recovery rate {obj.recovery_rate_pct}%.")
    messages.info(request, "No vendor credit note was drafted: accounting.Bill has no `kind` "
                           "field, so there is no document to raise. That is a Module 2/6 change.")
    return redirect("scm:warrantyclaim_detail", pk=pk)
