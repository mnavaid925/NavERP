"""Accounting 2.3 Accounts Payable — Payments views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.views._helpers import _first_account, _open_period, _recompute_doc_status, _reverse_journal_entry
from apps.accounting.models import (
    Bill,
    JournalEntry,
    JournalLine,
    Payment,
    ZERO,
)
from apps.accounting.forms import (
    PaymentForm,
)


@login_required
def payment_schedule(request):
    """2.3 Payment Scheduling — open bills (approved/partial) ordered by due date, with each bill's
    early-payment discount window from its PaymentTerm. Suggested pay date = the discount deadline
    when a discount is still capturable today, else the due date; a running net-outflow total helps
    time payments against cash. Read-only — reuses Bill + PaymentTerm, no new model."""
    tenant = request.tenant
    rows = []
    totals = {"outstanding": ZERO, "discount": ZERO, "net": ZERO}
    if tenant is not None:
        today = timezone.localdate()
        bills = (Bill.objects.filter(tenant=tenant, status__in=Bill.OPEN_STATUSES)
                 .select_related("party", "payment_terms")
                 .annotate(paid_agg=Sum("allocations__allocated_amount",
                                        filter=Q(allocations__payment__status="confirmed")))
                 .order_by("due_date", "id"))
        running = ZERO
        for b in bills:
            outstanding = (b.total or ZERO) - (b.paid_agg or ZERO)
            if outstanding <= ZERO:
                continue
            term = b.payment_terms
            discount, deadline, suggested = ZERO, None, b.due_date
            if term and term.discount_pct and term.discount_days and b.bill_date:
                deadline = b.bill_date + timedelta(days=term.discount_days)
                if deadline >= today:  # early-payment discount still capturable
                    discount = (outstanding * term.discount_pct / 100).quantize(Decimal("0.01"))
                    suggested = deadline
            net = outstanding - discount
            running += net
            rows.append({"bill": b, "outstanding": outstanding, "discount": discount,
                         "deadline": deadline, "suggested": suggested, "net": net, "running": running,
                         "overdue": bool(b.due_date and b.due_date < today)})
            totals["outstanding"] += outstanding
            totals["discount"] += discount
            totals["net"] += net
    return render(request, "accounting/payable/payment/schedule.html",
                  {"rows": rows, "totals": totals, "today": timezone.localdate()})


# ============================================================== 2.3+2.4 — Payments
@login_required
def payment_list(request):
    return crud_list(
        request, Payment.objects.filter(tenant=request.tenant).select_related("party", "bank_account"),
        "accounting/payable/payment/list.html",
        search_fields=["number", "party__name"],
        filters=[("direction", "direction", False), ("status", "status", False),
                 ("payment_method", "payment_method", False)],
        extra_context={"direction_choices": Payment.DIRECTION_CHOICES,
                       "status_choices": Payment.STATUS_CHOICES,
                       "method_choices": Payment.METHOD_CHOICES},
    )


@login_required
def payment_create(request):
    return crud_create(request, form_class=PaymentForm, template="accounting/payable/payment/form.html",
                       success_url="accounting:payment_list")


@login_required
def payment_detail(request, pk):
    obj = get_object_or_404(
        Payment.objects.select_related("party", "bank_account", "currency", "journal_entry"),
        pk=pk, tenant=request.tenant,
    )
    return render(request, "accounting/payable/payment/detail.html", {
        "obj": obj,
        "allocations": obj.allocations.select_related("invoice", "bill"),
        "unallocated": obj.unallocated(),
    })


@login_required
def payment_edit(request, pk):
    payment = get_object_or_404(Payment, pk=pk, tenant=request.tenant)
    if payment.is_locked:
        messages.error(request, "A confirmed or void payment cannot be edited.")
        return redirect("accounting:payment_detail", pk=pk)
    return crud_edit(request, model=Payment, pk=pk, form_class=PaymentForm,
                     template="accounting/payable/payment/form.html", success_url="accounting:payment_list")


@login_required
@require_POST
def payment_delete(request, pk):
    payment = get_object_or_404(Payment, pk=pk, tenant=request.tenant)
    if payment.status != "draft":
        messages.error(request, "Only a draft payment can be deleted.")
        return redirect("accounting:payment_detail", pk=pk)
    return crud_delete(request, model=Payment, pk=pk, success_url="accounting:payment_list")


@tenant_admin_required
@require_POST
def payment_confirm(request, pk):
    payment = get_object_or_404(Payment, pk=pk, tenant=request.tenant)
    if payment.status != "draft":
        messages.info(request, "This payment is not in a draft state.")
        return redirect("accounting:payment_detail", pk=pk)
    je = None
    bank_gl = payment.bank_account.gl_account or _first_account(request.tenant, "asset", "1000")
    if payment.direction == "in":
        counter = _first_account(request.tenant, "asset", "1100") or _first_account(request.tenant, "asset")
    else:
        counter = _first_account(request.tenant, "liability", "2000") or _first_account(request.tenant, "liability")
    if bank_gl and counter and bank_gl != counter and payment.amount > ZERO:
        with transaction.atomic():
            je = JournalEntry.objects.create(
                tenant=request.tenant, entry_type="payment", status="posted",
                fiscal_period=_open_period(request.tenant), entry_date=payment.payment_date,
                description=f"Payment {payment.number} — {payment.party.name}", reference=payment.number,
                created_by=request.user, approved_by=request.user, posted_at=timezone.now(),
            )
            if payment.direction == "in":  # Dr Bank / Cr AR
                JournalLine.objects.create(entry=je, gl_account=bank_gl, debit=payment.amount, credit=ZERO,
                                           description=f"Receipt {payment.number}", party=payment.party)
                JournalLine.objects.create(entry=je, gl_account=counter, debit=ZERO, credit=payment.amount,
                                           description=f"AR settle {payment.number}", party=payment.party)
            else:  # Dr AP / Cr Bank
                JournalLine.objects.create(entry=je, gl_account=counter, debit=payment.amount, credit=ZERO,
                                           description=f"AP settle {payment.number}", party=payment.party)
                JournalLine.objects.create(entry=je, gl_account=bank_gl, debit=ZERO, credit=payment.amount,
                                           description=f"Payment {payment.number}", party=payment.party)
            payment.journal_entry = je
            payment.status = "confirmed"
            payment.save(update_fields=["journal_entry", "status", "updated_at"])
    else:
        payment.status = "confirmed"
        payment.save(update_fields=["status", "updated_at"])
    # Now that the payment is confirmed, the docs it pays move to partial/paid.
    for alloc in payment.allocations.select_related("invoice", "bill"):
        _recompute_doc_status(alloc.invoice, alloc.bill)
    write_audit_log(request.user, payment, "update", {"action": "confirm", "journal_entry": je.number if je else None})
    messages.success(request, f"Payment {payment.number} confirmed.")
    return redirect("accounting:payment_detail", pk=pk)


@tenant_admin_required
@require_POST
def payment_void(request, pk):
    payment = get_object_or_404(Payment.objects.select_related("journal_entry"), pk=pk, tenant=request.tenant)
    if payment.status != "confirmed":
        messages.error(request, "Only a confirmed payment can be voided.")
        return redirect("accounting:payment_detail", pk=pk)
    with transaction.atomic():
        reversal = None
        # Reverse the GL effect of the confirmation so the ledger stays balanced (code-review #2).
        if payment.journal_entry_id and payment.journal_entry.status == "posted":
            reversal = _reverse_journal_entry(request.tenant, request.user, payment.journal_entry)
        payment.status = "void"
        payment.save(update_fields=["status", "updated_at"])
    # The voided payment no longer counts — docs it had paid revert toward sent/approved.
    for alloc in payment.allocations.select_related("invoice", "bill"):
        _recompute_doc_status(alloc.invoice, alloc.bill)
    write_audit_log(request.user, payment, "update",
                    {"action": "void", "reversal": reversal.number if reversal else None})
    messages.success(request, f"Payment {payment.number} voided{' — GL reversal posted' if reversal else ''}.")
    return redirect("accounting:payment_detail", pk=pk)
