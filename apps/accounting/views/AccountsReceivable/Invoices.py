"""Accounting 2.4 Accounts Receivable — Invoices views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.views._helpers import _first_account, _need_tenant, _open_period
from apps.accounting.models import (
    CustomerProfile,
    Invoice,
    JournalEntry,
    JournalLine,
    ZERO,
)
from apps.accounting.forms import (
    InvoiceForm,
    InvoiceLineFormSet,
)


def _customer_parties(tenant):
    return Party.objects.filter(tenant=tenant, roles__role="customer").distinct()


# ==================================================================== 2.4 AR — Invoices
@login_required
def invoice_list(request):
    return crud_list(
        request, Invoice.objects.filter(tenant=request.tenant).select_related("party", "currency"),
        "accounting/receivable/invoice/list.html",
        search_fields=["number", "party__name"],
        filters=[("status", "status", False), ("kind", "kind", False), ("party", "party_id", True)],
        extra_context={"status_choices": Invoice.STATUS_CHOICES, "kind_choices": Invoice.KIND_CHOICES,
                       "parties": _customer_parties(request.tenant)},
    )


@login_required
def invoice_create(request):
    return _invoice_form(request, instance=None)


@login_required
def invoice_edit(request, pk):
    inv = get_object_or_404(Invoice, pk=pk, tenant=request.tenant)
    if inv.is_locked:
        messages.error(request, "A paid or void invoice cannot be edited. Issue a credit note instead.")
        return redirect("accounting:invoice_detail", pk=pk)
    return _invoice_form(request, instance=inv)


def _invoice_form(request, instance):
    if instance is None and _need_tenant(request):
        return redirect("accounting:invoice_list")
    is_edit = instance is not None
    over_limit = False
    if request.method == "POST":
        form = InvoiceForm(request.POST, instance=instance, tenant=request.tenant)
        formset = InvoiceLineFormSet(request.POST, instance=instance, form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                inv = form.save(commit=False)
                inv.tenant = request.tenant
                inv.save()
                formset.instance = inv
                formset.save()
                inv.recalc_totals()
            write_audit_log(request.user, inv, "update" if is_edit else "create")
            messages.success(request, f"Invoice {inv.number} saved.")
            return redirect("accounting:invoice_detail", pk=inv.pk)
    else:
        form = InvoiceForm(instance=instance, tenant=request.tenant)
        formset = InvoiceLineFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "accounting/receivable/invoice/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance,
                   "over_limit": over_limit})


@login_required
def invoice_detail(request, pk):
    obj = get_object_or_404(
        Invoice.objects.select_related("party", "payment_terms", "currency", "journal_entry"),
        pk=pk, tenant=request.tenant,
    )
    profile = CustomerProfile.objects.filter(tenant=request.tenant, party=obj.party).first()
    over_limit = False
    if profile and profile.credit_limit:
        outstanding = (Invoice.objects.filter(tenant=request.tenant, party=obj.party,
                                              status__in=Invoice.OPEN_STATUSES)
                       .aggregate(s=Sum("total"))["s"] or ZERO)
        over_limit = outstanding > profile.credit_limit
    return render(request, "accounting/receivable/invoice/detail.html", {
        "obj": obj,
        "lines": obj.lines.select_related("gl_account"),
        "allocations": obj.allocations.select_related("payment"),
        "amount_paid": obj.amount_paid(),
        "balance_due": obj.balance_due(),
        "over_limit": over_limit,
    })


@login_required
@require_POST
def invoice_delete(request, pk):
    inv = get_object_or_404(Invoice, pk=pk, tenant=request.tenant)
    if inv.status != "draft":
        messages.error(request, "Only a draft invoice can be deleted.")
        return redirect("accounting:invoice_detail", pk=pk)
    return crud_delete(request, model=Invoice, pk=pk, success_url="accounting:invoice_list")


@tenant_admin_required
@require_POST
def invoice_post(request, pk):
    inv = get_object_or_404(Invoice, pk=pk, tenant=request.tenant)
    if inv.status != "draft":
        messages.info(request, "This invoice has already been issued.")
        return redirect("accounting:invoice_detail", pk=pk)
    inv.recalc_totals(save=False)
    je = None
    ar = _first_account(request.tenant, "asset", "1100") or _first_account(request.tenant, "asset")
    income = _first_account(request.tenant, "income")
    if ar and income and inv.total > ZERO:
        with transaction.atomic():
            je = JournalEntry.objects.create(
                tenant=request.tenant, entry_type="invoice", status="posted",
                fiscal_period=_open_period(request.tenant), entry_date=inv.issue_date,
                description=f"Invoice {inv.number} — {inv.party.name}", reference=inv.number,
                created_by=request.user, approved_by=request.user, posted_at=timezone.now(),
            )
            JournalLine.objects.create(entry=je, gl_account=ar, debit=inv.total, credit=ZERO,
                                       description=f"AR {inv.number}", party=inv.party)
            JournalLine.objects.create(entry=je, gl_account=income, debit=ZERO, credit=inv.total,
                                       description=f"Revenue {inv.number}", party=inv.party)
            inv.journal_entry = je
            inv.status = "sent"
            inv.save()
    else:
        inv.status = "sent"
        inv.save()
        messages.warning(request, "Issued without a GL entry — configure an AR (1100) and an income "
                                  "account so invoices post to the ledger automatically.")
    write_audit_log(request.user, inv, "update", {"action": "post", "journal_entry": je.number if je else None})
    messages.success(request, f"Invoice {inv.number} issued{' and posted to the GL' if je else ''}.")
    return redirect("accounting:invoice_detail", pk=pk)
