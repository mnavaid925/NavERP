"""CRM 1.7 Finance & Billing Management — DealInvoices views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    DealInvoice,
    Expense,
    Quote,
)
from apps.crm.forms import (
    DealInvoiceForm,
)
from apps.accounting.models import Currency, Invoice, InvoiceLine, PaymentAllocation


# ------------------------------------------------------------ 1.7 Invoicing (DealInvoice)
# CRM-owned wrapper over the accounting ledger (L29): the conversion creates a DRAFT
# accounting.Invoice; issuing/GL-posting + cash application stay in Accounting (draft hand-off).
_CCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "INR": "₹",
                "AUD": "$", "CAD": "$", "CHF": "CHF", "CNY": "¥"}


def _ccy_symbol(code):
    """A display symbol for a currency code so an auto-created Currency isn't symbol-less."""
    return _CCY_SYMBOLS.get(code, "")


@login_required
def dealinvoice_list(request):
    # Annotate confirmed amount-paid + derived balance via a correlated Subquery so the list does
    # NOT fire one PaymentAllocation aggregate per row (performance-review N+1). Matches the
    # property's ``payment__status="confirmed"`` filter exactly. invoice.total is free (select_related).
    dec = DecimalField(max_digits=18, decimal_places=2)
    paid_sq = Subquery(
        PaymentAllocation.objects.filter(invoice=OuterRef("invoice"), payment__status="confirmed")
        .values("invoice").annotate(t=Sum("allocated_amount")).values("t"),
        output_field=DecimalField(max_digits=18, decimal_places=2))
    qs = (DealInvoice.objects.filter(tenant=request.tenant)
          .select_related("opportunity", "account", "invoice", "recurring_invoice")
          .annotate(amt_paid=Coalesce(paid_sq, Value(Decimal("0")), output_field=dec))
          .annotate(bal_due=Coalesce(F("invoice__total"), Value(Decimal("0")), output_field=dec)
                    - F("amt_paid")))
    return crud_list(
        request, qs,
        "crm/finance/dealinvoice/list.html",
        search_fields=["number", "account__name", "opportunity__name", "invoice__number"],
        filters=[("status", "invoice__status", False)],
        extra_context={"status_choices": Invoice.STATUS_CHOICES},
    )


@login_required
@require_POST
def dealinvoice_from_quote(request, quote_pk):
    """One-click quote→invoice conversion (1.7 Invoicing). Generates a DRAFT accounting.Invoice
    from an ACCEPTED quote — carrying line items, per-line + quote-level discount, and tax — and
    wraps it in a DealInvoice. The net unit price folds both discounts so invoice.total == quote.total."""
    quote = get_object_or_404(
        Quote.objects.select_related("account", "opportunity"), pk=quote_pk, tenant=request.tenant)
    existing = DealInvoice.objects.filter(tenant=request.tenant, quote=quote).first()
    if existing:  # idempotent — a converted quote jumps to its existing wrapper
        messages.info(request, f"This quote was already converted ({existing.number}).")
        return redirect("crm:dealinvoice_detail", pk=existing.pk)
    if quote.status != "accepted":
        messages.error(request, "Only an accepted quote can be converted to an invoice.")
        return redirect("crm:quote_detail", pk=quote.pk)
    if quote.account_id is None:
        messages.error(request, "This quote has no account (bill-to). Set an account before converting.")
        return redirect("crm:quote_detail", pk=quote.pk)
    lines = list(quote.lines.all())
    if not lines:
        messages.error(request, "This quote has no line items to invoice.")
        return redirect("crm:quote_detail", pk=quote.pk)

    code = (quote.currency_code or "USD").upper()[:3]  # clamp to the Currency.code max_length
    quote_disc = (Decimal(100) - Decimal(quote.discount_pct or 0)) / Decimal(100)
    with transaction.atomic():
        currency, _ = Currency.objects.get_or_create(
            code=code, defaults={"name": code, "symbol": _ccy_symbol(code)})
        inv = Invoice.objects.create(
            tenant=request.tenant, party=quote.account, issue_date=timezone.localdate(),
            status="draft", currency=currency,
            notes=f"Generated from quote {quote.number}" + (f" — {quote.name}" if quote.name else ""))
        for ln in lines:
            line_disc = (Decimal(100) - Decimal(ln.discount_pct or 0)) / Decimal(100)
            net_unit = (Decimal(ln.unit_price or 0) * line_disc * quote_disc).quantize(Decimal("0.01"))
            InvoiceLine.objects.create(
                invoice=inv, description=(ln.description or "Item")[:255],
                quantity=(ln.quantity or Decimal(1)), unit_price=net_unit,
                tax_rate_pct=(ln.tax_pct or Decimal(0)))
        inv.recalc_totals()
        deal = DealInvoice.objects.create(
            tenant=request.tenant, opportunity=quote.opportunity, quote=quote,
            account=quote.account, invoice=inv, notes=f"Converted from quote {quote.number}.")
    write_audit_log(request.user, deal, "create",
                    changes={"action": "convert_quote", "quote": quote.number, "invoice": inv.number})
    messages.success(request, f"Quote {quote.number} converted → invoice {inv.number} (draft). "
                              "Issue it from Accounting to post it to the ledger.")
    return redirect("crm:dealinvoice_detail", pk=deal.pk)


@login_required
def dealinvoice_create(request):
    # Custom create (not crud_create): ``invoice`` is editable=False on the model, so its value is
    # taken from the form's explicit field and set here. The conversion action is the usual path.
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = DealInvoiceForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.invoice = form.cleaned_data.get("invoice")
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Deal invoice {obj.number} created.")
            return redirect("crm:dealinvoice_detail", pk=obj.pk)
    else:
        form = DealInvoiceForm(tenant=request.tenant)
    return render(request, "crm/finance/dealinvoice/form.html", {"form": form, "is_edit": False})


@login_required
def dealinvoice_detail(request, pk):
    obj = get_object_or_404(
        DealInvoice.objects.select_related(
            "opportunity", "account", "quote", "invoice", "invoice__currency", "recurring_invoice"),
        pk=pk, tenant=request.tenant)
    # Each ledger allocation against the linked invoice is a partial/milestone payment.
    allocations = (obj.invoice.allocations.select_related("payment") if obj.invoice_id else [])
    receipts = obj.receipts.select_related("payment")
    # Deal margin = revenue (opportunity amount) − non-billable, non-rejected expenses on the deal.
    margin = None
    if obj.opportunity_id:
        revenue = obj.opportunity.amount or Decimal("0")
        cost = (Expense.objects.filter(tenant=request.tenant, opportunity_id=obj.opportunity_id,
                                       is_billable=False).exclude(status="rejected")
                .aggregate(s=Sum("amount"))["s"] or Decimal("0"))
        margin = {"revenue": revenue, "cost": cost, "profit": revenue - cost,
                  "pct": ((revenue - cost) / revenue * 100) if revenue else None}
    # Precompute paid/balance once (the property hits the DB) so the template doesn't call
    # amount_paid() twice — once directly and once inside balance_due (performance-review #2).
    amount_paid = obj.amount_paid
    balance_due = obj.invoice_total - amount_paid
    return render(request, "crm/finance/dealinvoice/detail.html", {
        "obj": obj, "allocations": allocations, "receipts": receipts, "margin": margin,
        "amount_paid": amount_paid, "balance_due": balance_due,
    })


@login_required
def dealinvoice_edit(request, pk):
    obj = get_object_or_404(DealInvoice, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = DealInvoiceForm(request.POST, instance=obj, tenant=request.tenant, editing=True)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, "Updated successfully.")
            return redirect("crm:dealinvoice_detail", pk=obj.pk)
    else:
        form = DealInvoiceForm(instance=obj, tenant=request.tenant, editing=True)
    return render(request, "crm/finance/dealinvoice/form.html", {"form": form, "obj": obj, "is_edit": True})


@login_required
@require_POST
def dealinvoice_delete(request, pk):
    # Deletes the CRM wrapper ONLY — the ledger invoice in Accounting is left untouched.
    return crud_delete(request, model=DealInvoice, pk=pk, success_url="crm:dealinvoice_list")
