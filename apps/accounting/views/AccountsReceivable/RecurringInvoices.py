"""Accounting 2.4 Accounts Receivable — RecurringInvoices views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    Invoice,
    InvoiceLine,
    RecurringInvoice,
)
from apps.accounting.forms import (
    RecurringInvoiceForm,
)


# ===================================================== 2.4 Recurring Invoicing
@login_required
def recurringinvoice_list(request):
    return crud_list(
        request,
        RecurringInvoice.objects.filter(tenant=request.tenant)
        .select_related("party", "currency", "payment_terms"),
        "accounting/receivable/recurringinvoice/list.html",
        search_fields=["number", "description", "party__name"],
        filters=[("status", "status", False), ("cadence", "cadence", False)],
        extra_context={"status_choices": RecurringInvoice.STATUS_CHOICES,
                       "cadence_choices": RecurringInvoice.CADENCE_CHOICES},
    )


@login_required
def recurringinvoice_create(request):
    return crud_create(request, form_class=RecurringInvoiceForm,
                       template="accounting/receivable/recurringinvoice/form.html",
                       success_url="accounting:recurringinvoice_list")


@login_required
def recurringinvoice_detail(request, pk):
    obj = get_object_or_404(
        RecurringInvoice.objects.select_related("party", "currency", "payment_terms"),
        pk=pk, tenant=request.tenant)
    generated = (Invoice.objects.filter(tenant=request.tenant, recurring_invoice=obj)
                 .order_by("-issue_date", "-id")[:20])
    return render(request, "accounting/receivable/recurringinvoice/detail.html",
                  {"obj": obj, "generated": generated})


@login_required
def recurringinvoice_edit(request, pk):
    return crud_edit(request, model=RecurringInvoice, pk=pk, form_class=RecurringInvoiceForm,
                     template="accounting/receivable/recurringinvoice/form.html",
                     success_url="accounting:recurringinvoice_list")


@login_required
@require_POST
def recurringinvoice_delete(request, pk):
    return crud_delete(request, model=RecurringInvoice, pk=pk,
                       success_url="accounting:recurringinvoice_list")


@login_required
@require_POST
def recurringinvoice_generate(request, pk):
    """Generate the next draft Invoice from an active schedule and advance its next run date."""
    rec = get_object_or_404(RecurringInvoice, pk=pk, tenant=request.tenant)
    if rec.status != "active":
        messages.error(request, "Only an active schedule can generate invoices.")
        return redirect("accounting:recurringinvoice_detail", pk=rec.pk)
    with transaction.atomic():
        issue = rec.next_run_date or timezone.localdate()
        days_due = rec.payment_terms.days_due if rec.payment_terms else 30
        inv = Invoice.objects.create(
            tenant=request.tenant, party=rec.party, kind="invoice", issue_date=issue,
            due_date=issue + timedelta(days=days_due), status="draft",
            currency=rec.currency, payment_terms=rec.payment_terms, recurring_invoice=rec,
            notes=f"Auto-generated from recurring schedule {rec.number}.")
        InvoiceLine.objects.create(invoice=inv, description=rec.description, quantity=1,
                                   unit_price=rec.amount)
        inv.recalc_totals()
        rec.occurrences_generated += 1
        rec.advance()  # anchored to start_date via run_date_for(occurrences_generated)
        rec.last_generated_at = timezone.now()
        rec.save(update_fields=["next_run_date", "occurrences_generated", "last_generated_at",
                                "updated_at"])
    write_audit_log(request.user, rec, "update", {"action": "generate", "invoice": inv.number})
    messages.success(request, f"Draft invoice {inv.number} created from {rec.number}.")
    return redirect("accounting:invoice_detail", pk=inv.pk)
