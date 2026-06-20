"""Accounting & Finance (Module 2) views — function-based, ``@login_required``, tenant-scoped.

Plain CRUD reuses the shared ``apps.core.crud`` helpers (search + int-FK-guarded filters +
windowed pagination + audit). The ledger documents (JournalEntry / Invoice / Bill) use custom
create/edit views because they own inline line-item formsets, and the workflow transitions
(post / void / approve / confirm / close / reconcile) are POST-only action views that enforce the
double-entry invariants and write an ``AuditLog`` row. Privileged transitions are gated with
``@tenant_admin_required`` (L27).
"""
import csv
import io
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log

from .forms import (
    BankAccountForm,
    BankTransactionForm,
    BillForm,
    BillLineFormSet,
    CsvImportForm,
    CurrencyForm,
    CustomerProfileForm,
    ExchangeRateForm,
    FiscalPeriodForm,
    GLAccountForm,
    InvoiceForm,
    InvoiceLineFormSet,
    JournalEntryForm,
    JournalLineFormSet,
    PaymentAllocationForm,
    PaymentForm,
    PaymentTermForm,
    ReconciliationMatchForm,
    VendorProfileForm,
)
from .models import (
    ZERO,
    BankAccount,
    BankTransaction,
    Bill,
    Currency,
    CustomerProfile,
    ExchangeRate,
    FiscalPeriod,
    GLAccount,
    Invoice,
    JournalEntry,
    JournalLine,
    Payment,
    PaymentAllocation,
    PaymentTerm,
    ReconciliationMatch,
    VendorProfile,
)


# --------------------------------------------------------------------------- helpers
def _need_tenant(request):
    """True (and flashes) when there is no active tenant workspace to write into."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return True
    return False


def _customer_parties(tenant):
    return Party.objects.filter(tenant=tenant, roles__role="customer").distinct()


def _vendor_parties(tenant):
    return Party.objects.filter(tenant=tenant, roles__role="vendor").distinct()


def _first_account(tenant, account_type, code_prefix=None):
    qs = GLAccount.objects.filter(tenant=tenant, account_type=account_type, is_active=True)
    if code_prefix:
        hit = qs.filter(code__startswith=code_prefix).first()
        if hit:
            return hit
    return qs.first()


def _open_period(tenant):
    return FiscalPeriod.objects.filter(tenant=tenant, status="open").order_by("-start_date").first()


def _reverse_journal_entry(tenant, user, original):
    """Post a balanced reversal of a posted ``JournalEntry`` (debits/credits swapped) and mark the
    original ``void``. The single point of truth for voiding any posted GL entry (manual JE *or* the
    JE behind a payment) so the ledger always stays balanced. Caller wraps this in atomic()."""
    reversal = JournalEntry.objects.create(
        tenant=tenant, entry_type="reversal", status="posted",
        fiscal_period=original.fiscal_period if (original.fiscal_period and original.fiscal_period.is_open) else _open_period(tenant),
        entry_date=timezone.localdate(), description=f"Reversal of {original.number}",
        reversal_of=original, created_by=user, approved_by=user, posted_at=timezone.now(),
    )
    for ln in original.lines.all():
        JournalLine.objects.create(
            entry=reversal, gl_account=ln.gl_account, debit=ln.credit, credit=ln.debit,
            description=f"Reversal: {ln.description}", party=ln.party, org_unit=ln.org_unit,
            currency=ln.currency,
        )
    original.status = "void"
    original.save(update_fields=["status", "updated_at"])
    return reversal


# ============================================================== 2.1 Dashboard + reports
@login_required
def accounting_dashboard(request):
    tenant = request.tenant
    stats = {"cash_position": ZERO, "ar_outstanding": ZERO, "ap_outstanding": ZERO,
             "overdue_count": 0}
    overdue_invoices = overdue_bills = recent_je = []
    cash_labels, cash_data = [], []
    if tenant is not None:
        today = timezone.localdate()
        # Cash position in TWO queries (not N+1): one grouped aggregate of all bank-txn movement
        # keyed by account, plus the fixed opening balances (perf-review C-1).
        banks = list(BankAccount.objects.filter(tenant=tenant))
        net_by_bank = {
            r["bank_account_id"]: (r["credit"] or ZERO) - (r["debit"] or ZERO)
            for r in BankTransaction.objects.filter(tenant=tenant).values("bank_account_id")
            .annotate(credit=Sum("amount", filter=Q(direction="credit")),
                      debit=Sum("amount", filter=Q(direction="debit")))
        }
        stats["cash_position"] = sum(
            ((b.opening_balance or ZERO) + net_by_bank.get(b.pk, ZERO) for b in banks), ZERO)
        stats["ar_outstanding"] = (
            Invoice.objects.filter(tenant=tenant, status__in=Invoice.OPEN_STATUSES)
            .aggregate(s=Sum("total"))["s"] or ZERO
        )
        stats["ap_outstanding"] = (
            Bill.objects.filter(tenant=tenant, status__in=Bill.OPEN_STATUSES)
            .aggregate(s=Sum("total"))["s"] or ZERO
        )
        overdue_invoices = list(
            Invoice.objects.filter(tenant=tenant, status__in=Invoice.OPEN_STATUSES,
                                   due_date__lt=today).select_related("party")[:10]
        )
        overdue_bills = list(
            Bill.objects.filter(tenant=tenant, status__in=Bill.OPEN_STATUSES,
                                due_date__lt=today).select_related("party")[:10]
        )
        stats["overdue_count"] = len(overdue_invoices) + len(overdue_bills)
        recent_je = list(
            JournalEntry.objects.filter(tenant=tenant, status="posted")
            .select_related("fiscal_period").order_by("-entry_date", "-id")[:5]
        )
        # 6-week net-cash trend (Mon-anchored buckets).
        week_start = today - timedelta(days=today.weekday())
        for i in range(5, -1, -1):
            start = week_start - timedelta(weeks=i)
            end = start + timedelta(days=6)
            agg = BankTransaction.objects.filter(
                tenant=tenant, transaction_date__range=(start, end)
            ).aggregate(credit=Sum("amount", filter=Q(direction="credit")),
                        debit=Sum("amount", filter=Q(direction="debit")))
            net = (agg["credit"] or ZERO) - (agg["debit"] or ZERO)
            cash_labels.append(start.strftime("%b %d"))
            cash_data.append(float(net))
    return render(request, "accounting/dashboard.html", {
        "stats": stats,
        "overdue_invoices": overdue_invoices,
        "overdue_bills": overdue_bills,
        "recent_je": recent_je,
        "today": timezone.localdate(),
        "cash_labels": cash_labels,
        "cash_data": cash_data,
    })


@login_required
def trial_balance(request):
    tenant = request.tenant
    rows, total_debit, total_credit = [], ZERO, ZERO
    if tenant is not None:
        agg = (
            JournalLine.objects.filter(entry__tenant=tenant, entry__status="posted")
            .values("gl_account", "gl_account__code", "gl_account__name", "gl_account__normal_balance")
            .annotate(debit=Sum("debit"), credit=Sum("credit"))
            .order_by("gl_account__code")
        )
        for r in agg:
            debit, credit = r["debit"] or ZERO, r["credit"] or ZERO
            balance = debit - credit
            rows.append({
                "code": r["gl_account__code"], "name": r["gl_account__name"],
                "debit": debit, "credit": credit,
                "balance_debit": balance if balance > 0 else ZERO,
                "balance_credit": -balance if balance < 0 else ZERO,
            })
            total_debit += debit
            total_credit += credit
    return render(request, "accounting/trial_balance.html", {
        "rows": rows, "total_debit": total_debit, "total_credit": total_credit,
        "balanced": total_debit == total_credit,
    })


def _aging(rows, due_attr, today):
    """Bucket a list of documents by overdue age and group by party. Returns (party_rows, totals)."""
    buckets = ("current", "d1_30", "d31_60", "d61_90", "d90_plus")
    by_party = {}
    totals = {b: ZERO for b in buckets}
    totals["total"] = ZERO
    for doc in rows:
        due = getattr(doc, due_attr)
        # `paid_agg` is annotated on the queryset by the caller (perf-review C-2) so this loop
        # issues NO per-document aggregate query.
        amount = (doc.total or ZERO) - (doc.paid_agg or ZERO)
        if amount <= ZERO:
            continue
        days = (today - due).days if due else 0
        if days <= 0:
            b = "current"
        elif days <= 30:
            b = "d1_30"
        elif days <= 60:
            b = "d31_60"
        elif days <= 90:
            b = "d61_90"
        else:
            b = "d90_plus"
        name = doc.party.name
        prow = by_party.setdefault(name, {k: ZERO for k in buckets} | {"total": ZERO, "party": name})
        prow[b] += amount
        prow["total"] += amount
        totals[b] += amount
        totals["total"] += amount
    return sorted(by_party.values(), key=lambda r: r["party"]), totals


@login_required
def ar_aging(request):
    tenant = request.tenant
    party_rows, totals = [], {}
    if tenant is not None:
        docs = list(Invoice.objects.filter(tenant=tenant, status__in=Invoice.OPEN_STATUSES)
                    .select_related("party")
                    .annotate(paid_agg=Sum("allocations__allocated_amount")))
        party_rows, totals = _aging(docs, "due_date", timezone.localdate())
    return render(request, "accounting/ar_aging.html", {"party_rows": party_rows, "totals": totals})


@login_required
def ap_aging(request):
    tenant = request.tenant
    party_rows, totals = [], {}
    if tenant is not None:
        docs = list(Bill.objects.filter(tenant=tenant, status__in=Bill.OPEN_STATUSES)
                    .select_related("party")
                    .annotate(paid_agg=Sum("allocations__allocated_amount")))
        party_rows, totals = _aging(docs, "due_date", timezone.localdate())
    return render(request, "accounting/ap_aging.html", {"party_rows": party_rows, "totals": totals})


@login_required
def gl_account_ledger(request, account_pk):
    account = get_object_or_404(GLAccount, pk=account_pk, tenant=request.tenant)
    lines = (JournalLine.objects.filter(gl_account=account, entry__status="posted")
             .select_related("entry").order_by("entry__entry_date", "id"))
    running = ZERO
    rows = []
    for ln in lines:
        delta = (ln.debit - ln.credit) if account.normal_balance == "debit" else (ln.credit - ln.debit)
        running += delta
        rows.append({"line": ln, "running": running})
    return render(request, "accounting/gl_account_ledger.html", {"obj": account, "rows": rows})


# ============================================================ 2.2 GL — Chart of Accounts
@login_required
def glaccount_list(request):
    return crud_list(
        request, GLAccount.objects.filter(tenant=request.tenant).select_related("parent"),
        "accounting/glaccount_list.html",
        search_fields=["code", "name"],
        filters=[("account_type", "account_type", False), ("is_active", "is_active", False)],
        extra_context={"account_type_choices": GLAccount.ACCOUNT_TYPE_CHOICES},
    )


@login_required
def glaccount_create(request):
    return crud_create(request, form_class=GLAccountForm, template="accounting/glaccount_form.html",
                       success_url="accounting:glaccount_list")


@login_required
def glaccount_detail(request, pk):
    obj = get_object_or_404(GLAccount.objects.select_related("parent"), pk=pk, tenant=request.tenant)
    return render(request, "accounting/glaccount_detail.html", {
        "obj": obj,
        "children": obj.children.all(),
        "balance": obj.balance(),
        "has_lines": obj.journal_lines.exists(),
    })


@login_required
def glaccount_edit(request, pk):
    return crud_edit(request, model=GLAccount, pk=pk, form_class=GLAccountForm,
                     template="accounting/glaccount_form.html", success_url="accounting:glaccount_list")


@login_required
@require_POST
def glaccount_delete(request, pk):
    obj = get_object_or_404(GLAccount, pk=pk, tenant=request.tenant)
    if obj.journal_lines.exists():
        messages.error(request, "Cannot delete an account that has posted journal lines.")
        return redirect("accounting:glaccount_detail", pk=pk)
    return crud_delete(request, model=GLAccount, pk=pk, success_url="accounting:glaccount_list")


# ============================================================== 2.2 GL — Fiscal periods
@login_required
def fiscal_period_list(request):
    return crud_list(
        request, FiscalPeriod.objects.filter(tenant=request.tenant),
        "accounting/fiscal_period_list.html",
        search_fields=["name"],
        filters=[("status", "status", False), ("period_type", "period_type", False)],
        extra_context={"status_choices": FiscalPeriod.STATUS_CHOICES,
                       "period_type_choices": FiscalPeriod.PERIOD_TYPE_CHOICES},
    )


@login_required
def fiscal_period_create(request):
    return crud_create(request, form_class=FiscalPeriodForm, template="accounting/fiscal_period_form.html",
                       success_url="accounting:fiscal_period_list")


@login_required
def fiscal_period_detail(request, pk):
    obj = get_object_or_404(FiscalPeriod.objects.select_related("closed_by"), pk=pk, tenant=request.tenant)
    return render(request, "accounting/fiscal_period_detail.html", {
        "obj": obj,
        "entry_count": obj.journal_entries.count(),
    })


@login_required
def fiscal_period_edit(request, pk):
    return crud_edit(request, model=FiscalPeriod, pk=pk, form_class=FiscalPeriodForm,
                     template="accounting/fiscal_period_form.html", success_url="accounting:fiscal_period_list")


@login_required
@require_POST
def fiscal_period_delete(request, pk):
    return crud_delete(request, model=FiscalPeriod, pk=pk, success_url="accounting:fiscal_period_list")


@tenant_admin_required
@require_POST
def fiscal_period_close(request, pk):
    period = get_object_or_404(FiscalPeriod, pk=pk, tenant=request.tenant)
    if period.status != "open":
        messages.info(request, "This period is not open.")
        return redirect("accounting:fiscal_period_detail", pk=pk)
    draft = period.journal_entries.filter(status__in=["draft", "pending_approval"]).count()
    if draft:
        messages.error(request, f"Cannot close: {draft} unposted journal entr{'y' if draft == 1 else 'ies'} remain in this period.")
        return redirect("accounting:fiscal_period_detail", pk=pk)
    period.status = "closed"
    period.closed_by = request.user
    period.closed_at = timezone.now()
    period.save(update_fields=["status", "closed_by", "closed_at", "updated_at"])
    write_audit_log(request.user, period, "update", {"action": "close_period"})
    messages.success(request, f"{period.name} closed.")
    return redirect("accounting:fiscal_period_detail", pk=pk)


# =============================================================== 2.2 GL — Journal entries
@login_required
def journal_entry_list(request):
    return crud_list(
        request, JournalEntry.objects.filter(tenant=request.tenant),
        "accounting/journal_entry_list.html",
        search_fields=["number", "description", "reference"],
        filters=[("status", "status", False), ("entry_type", "entry_type", False)],
        extra_context={"status_choices": JournalEntry.STATUS_CHOICES,
                       "entry_type_choices": JournalEntry.ENTRY_TYPE_CHOICES},
    )


@login_required
def journal_entry_create(request):
    if _need_tenant(request):
        return redirect("accounting:journal_entry_list")
    if request.method == "POST":
        form = JournalEntryForm(request.POST, tenant=request.tenant)
        formset = JournalLineFormSet(request.POST, form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                entry = form.save(commit=False)
                entry.tenant = request.tenant
                entry.created_by = request.user
                entry.save()
                formset.instance = entry
                formset.save()
            write_audit_log(request.user, entry, "create")
            messages.success(request, f"Journal entry {entry.number} created (draft).")
            return redirect("accounting:journal_entry_detail", pk=entry.pk)
    else:
        form = JournalEntryForm(tenant=request.tenant)
        formset = JournalLineFormSet(form_kwargs={"tenant": request.tenant})
    return render(request, "accounting/journal_entry_form.html",
                  {"form": form, "formset": formset, "is_edit": False})


@login_required
def journal_entry_detail(request, pk):
    obj = get_object_or_404(
        JournalEntry.objects.select_related("fiscal_period", "created_by", "approved_by", "reversal_of"),
        pk=pk, tenant=request.tenant,
    )
    lines = obj.lines.select_related("gl_account", "party", "org_unit", "currency")
    debit_total, credit_total = obj.totals()
    return render(request, "accounting/journal_entry_detail.html", {
        "obj": obj, "lines": lines, "debit_total": debit_total, "credit_total": credit_total,
        "balanced": obj.is_balanced(),
    })


@login_required
def journal_entry_edit(request, pk):
    entry = get_object_or_404(JournalEntry, pk=pk, tenant=request.tenant)
    if entry.is_locked:
        messages.error(request, "A posted or void entry is immutable. Create a reversal instead.")
        return redirect("accounting:journal_entry_detail", pk=pk)
    if request.method == "POST":
        form = JournalEntryForm(request.POST, instance=entry, tenant=request.tenant)
        formset = JournalLineFormSet(request.POST, instance=entry, form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
            write_audit_log(request.user, entry, "update")
            messages.success(request, f"Journal entry {entry.number} updated.")
            return redirect("accounting:journal_entry_detail", pk=entry.pk)
    else:
        form = JournalEntryForm(instance=entry, tenant=request.tenant)
        formset = JournalLineFormSet(instance=entry, form_kwargs={"tenant": request.tenant})
    return render(request, "accounting/journal_entry_form.html",
                  {"form": form, "formset": formset, "is_edit": True, "obj": entry})


@login_required
@require_POST
def journal_entry_delete(request, pk):
    entry = get_object_or_404(JournalEntry, pk=pk, tenant=request.tenant)
    if entry.is_locked:
        messages.error(request, "A posted or void entry cannot be deleted.")
        return redirect("accounting:journal_entry_detail", pk=pk)
    return crud_delete(request, model=JournalEntry, pk=pk, success_url="accounting:journal_entry_list")


@tenant_admin_required
@require_POST
def journal_entry_post(request, pk):
    entry = get_object_or_404(JournalEntry, pk=pk, tenant=request.tenant)
    if entry.is_locked:
        messages.error(request, "This entry is already posted or void.")
        return redirect("accounting:journal_entry_detail", pk=pk)
    if not entry.is_balanced():
        messages.error(request, "Cannot post: debits must equal credits and be greater than zero.")
        return redirect("accounting:journal_entry_detail", pk=pk)
    if entry.fiscal_period and not entry.fiscal_period.is_open:
        messages.error(request, "Cannot post into a closed fiscal period.")
        return redirect("accounting:journal_entry_detail", pk=pk)
    entry.status = "posted"
    entry.posted_at = timezone.now()
    entry.approved_by = request.user
    entry.save(update_fields=["status", "posted_at", "approved_by", "updated_at"])
    write_audit_log(request.user, entry, "update", {"action": "post"})
    messages.success(request, f"{entry.number} posted.")
    return redirect("accounting:journal_entry_detail", pk=pk)


@tenant_admin_required
@require_POST
def journal_entry_void(request, pk):
    entry = get_object_or_404(JournalEntry, pk=pk, tenant=request.tenant)
    if entry.status != "posted":
        messages.error(request, "Only a posted entry can be voided.")
        return redirect("accounting:journal_entry_detail", pk=pk)
    with transaction.atomic():
        reversal = _reverse_journal_entry(request.tenant, request.user, entry)
    write_audit_log(request.user, entry, "update", {"action": "void", "reversal": reversal.number})
    messages.success(request, f"{entry.number} voided — reversal {reversal.number} posted.")
    return redirect("accounting:journal_entry_detail", pk=pk)


# ============================================================ 2.2 GL — Currencies (global)
@login_required
def currency_list(request):
    return crud_list(
        request, Currency.objects.all(), "accounting/currency_list.html",
        search_fields=["code", "name"],
        filters=[("is_active", "is_active", False)],
    )


@login_required
def currency_create(request):
    if request.method == "POST":
        form = CurrencyForm(request.POST)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Created successfully.")
            return redirect("accounting:currency_list")
    else:
        form = CurrencyForm()
    return render(request, "accounting/currency_form.html", {"form": form, "is_edit": False})


@login_required
def currency_detail(request, pk):
    obj = get_object_or_404(Currency, pk=pk)
    return render(request, "accounting/currency_detail.html", {"obj": obj})


@login_required
def currency_edit(request, pk):
    obj = get_object_or_404(Currency, pk=pk)
    if request.method == "POST":
        form = CurrencyForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, "Updated successfully.")
            return redirect("accounting:currency_list")
    else:
        form = CurrencyForm(instance=obj)
    return render(request, "accounting/currency_form.html", {"form": form, "obj": obj, "is_edit": True})


@login_required
@require_POST
def currency_delete(request, pk):
    obj = get_object_or_404(Currency, pk=pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Deleted successfully.")
    return redirect("accounting:currency_list")


# --------------------------------------------------------------- Exchange rates
@login_required
def exchange_rate_list(request):
    return crud_list(
        request, ExchangeRate.objects.filter(tenant=request.tenant).select_related("currency"),
        "accounting/exchange_rate_list.html",
        search_fields=["currency__code"],
        filters=[("currency", "currency_id", True), ("source", "source", False)],
        extra_context={"currencies": Currency.objects.filter(is_active=True),
                       "source_choices": ExchangeRate.SOURCE_CHOICES},
    )


@login_required
def exchange_rate_create(request):
    return crud_create(request, form_class=ExchangeRateForm, template="accounting/exchange_rate_form.html",
                       success_url="accounting:exchange_rate_list")


@login_required
def exchange_rate_detail(request, pk):
    obj = get_object_or_404(ExchangeRate.objects.select_related("currency"), pk=pk, tenant=request.tenant)
    return render(request, "accounting/exchange_rate_detail.html", {"obj": obj})


@login_required
def exchange_rate_edit(request, pk):
    return crud_edit(request, model=ExchangeRate, pk=pk, form_class=ExchangeRateForm,
                     template="accounting/exchange_rate_form.html", success_url="accounting:exchange_rate_list")


@login_required
@require_POST
def exchange_rate_delete(request, pk):
    return crud_delete(request, model=ExchangeRate, pk=pk, success_url="accounting:exchange_rate_list")


# =============================================================== 2.3 AP — Payment terms
@login_required
def payment_term_list(request):
    return crud_list(
        request, PaymentTerm.objects.filter(tenant=request.tenant),
        "accounting/payment_term_list.html",
        search_fields=["name"],
        filters=[("is_active", "is_active", False)],
    )


@login_required
def payment_term_create(request):
    return crud_create(request, form_class=PaymentTermForm, template="accounting/payment_term_form.html",
                       success_url="accounting:payment_term_list")


@login_required
def payment_term_detail(request, pk):
    obj = get_object_or_404(PaymentTerm, pk=pk, tenant=request.tenant)
    return render(request, "accounting/payment_term_detail.html", {"obj": obj})


@login_required
def payment_term_edit(request, pk):
    return crud_edit(request, model=PaymentTerm, pk=pk, form_class=PaymentTermForm,
                     template="accounting/payment_term_form.html", success_url="accounting:payment_term_list")


@login_required
@require_POST
def payment_term_delete(request, pk):
    return crud_delete(request, model=PaymentTerm, pk=pk, success_url="accounting:payment_term_list")


# ================================================================ 2.3 AP — Vendor profiles
@login_required
def vendor_profile_list(request):
    return crud_list(
        request, VendorProfile.objects.filter(tenant=request.tenant)
        .select_related("party", "payment_terms", "currency"),
        "accounting/vendor_profile_list.html",
        search_fields=["party__name"],
        filters=[("payment_terms", "payment_terms_id", True), ("is_1099", "is_1099", False),
                 ("is_active", "is_active", False)],
        extra_context={"payment_terms": PaymentTerm.objects.filter(tenant=request.tenant)},
    )


@login_required
def vendor_profile_create(request):
    return crud_create(request, form_class=VendorProfileForm, template="accounting/vendor_profile_form.html",
                       success_url="accounting:vendor_profile_list")


@login_required
def vendor_profile_detail(request, pk):
    obj = get_object_or_404(
        VendorProfile.objects.select_related("party", "payment_terms", "currency", "default_expense_account"),
        pk=pk, tenant=request.tenant,
    )
    bills = (Bill.objects.filter(tenant=request.tenant, party=obj.party)
             .order_by("-bill_date")[:5])
    return render(request, "accounting/vendor_profile_detail.html", {"obj": obj, "bills": bills})


@login_required
def vendor_profile_edit(request, pk):
    return crud_edit(request, model=VendorProfile, pk=pk, form_class=VendorProfileForm,
                     template="accounting/vendor_profile_form.html", success_url="accounting:vendor_profile_list")


@login_required
@require_POST
def vendor_profile_delete(request, pk):
    return crud_delete(request, model=VendorProfile, pk=pk, success_url="accounting:vendor_profile_list")


# ======================================================================= 2.3 AP — Bills
@login_required
def bill_list(request):
    return crud_list(
        request, Bill.objects.filter(tenant=request.tenant).select_related("party", "currency"),
        "accounting/bill_list.html",
        search_fields=["number", "party__name"],
        filters=[("status", "status", False), ("party", "party_id", True)],
        extra_context={"status_choices": Bill.STATUS_CHOICES, "parties": _vendor_parties(request.tenant)},
    )


@login_required
def bill_create(request):
    return _bill_form(request, instance=None)


@login_required
def bill_edit(request, pk):
    bill = get_object_or_404(Bill, pk=pk, tenant=request.tenant)
    if bill.is_locked:
        messages.error(request, "A paid or void bill cannot be edited.")
        return redirect("accounting:bill_detail", pk=pk)
    return _bill_form(request, instance=bill)


def _bill_form(request, instance):
    if instance is None and _need_tenant(request):
        return redirect("accounting:bill_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = BillForm(request.POST, request.FILES, instance=instance, tenant=request.tenant)
        formset = BillLineFormSet(request.POST, instance=instance, form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                bill = form.save(commit=False)
                bill.tenant = request.tenant
                bill.save()
                formset.instance = bill
                formset.save()
                bill.recalc_totals()
            write_audit_log(request.user, bill, "update" if is_edit else "create")
            messages.success(request, f"Bill {bill.number} saved.")
            return redirect("accounting:bill_detail", pk=bill.pk)
    else:
        form = BillForm(instance=instance, tenant=request.tenant)
        formset = BillLineFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "accounting/bill_form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def bill_detail(request, pk):
    obj = get_object_or_404(
        Bill.objects.select_related("party", "payment_terms", "currency", "approved_by", "document"),
        pk=pk, tenant=request.tenant,
    )
    return render(request, "accounting/bill_detail.html", {
        "obj": obj,
        "lines": obj.lines.select_related("gl_account"),
        "allocations": obj.allocations.select_related("payment"),
        "amount_paid": obj.amount_paid(),
        "balance_due": obj.balance_due(),
    })


@login_required
@require_POST
def bill_delete(request, pk):
    bill = get_object_or_404(Bill, pk=pk, tenant=request.tenant)
    if bill.status != "draft":
        messages.error(request, "Only a draft bill can be deleted.")
        return redirect("accounting:bill_detail", pk=pk)
    return crud_delete(request, model=Bill, pk=pk, success_url="accounting:bill_list")


@tenant_admin_required
@require_POST
def bill_approve(request, pk):
    bill = get_object_or_404(Bill, pk=pk, tenant=request.tenant)
    if bill.status not in ("draft", "pending_approval"):
        messages.info(request, "This bill is not awaiting approval.")
        return redirect("accounting:bill_detail", pk=pk)
    bill.status = "approved"
    bill.approved_by = request.user
    bill.save(update_fields=["status", "approved_by", "updated_at"])
    write_audit_log(request.user, bill, "update", {"action": "approve"})
    messages.success(request, f"Bill {bill.number} approved.")
    return redirect("accounting:bill_detail", pk=pk)


# ============================================================== 2.4 AR — Customer profiles
@login_required
def customer_profile_list(request):
    return crud_list(
        request, CustomerProfile.objects.filter(tenant=request.tenant)
        .select_related("party", "payment_terms", "currency"),
        "accounting/customer_profile_list.html",
        search_fields=["party__name"],
        filters=[("payment_terms", "payment_terms_id", True), ("credit_on_hold", "credit_on_hold", False),
                 ("is_active", "is_active", False)],
        extra_context={"payment_terms": PaymentTerm.objects.filter(tenant=request.tenant)},
    )


@login_required
def customer_profile_create(request):
    return crud_create(request, form_class=CustomerProfileForm, template="accounting/customer_profile_form.html",
                       success_url="accounting:customer_profile_list")


@login_required
def customer_profile_detail(request, pk):
    obj = get_object_or_404(
        CustomerProfile.objects.select_related("party", "payment_terms", "currency", "ar_account"),
        pk=pk, tenant=request.tenant,
    )
    invoices = (Invoice.objects.filter(tenant=request.tenant, party=obj.party)
                .order_by("-issue_date")[:5])
    outstanding = (Invoice.objects.filter(tenant=request.tenant, party=obj.party,
                                          status__in=Invoice.OPEN_STATUSES)
                   .aggregate(s=Sum("total"))["s"] or ZERO)
    return render(request, "accounting/customer_profile_detail.html", {
        "obj": obj, "invoices": invoices, "outstanding": outstanding,
        "over_limit": obj.credit_limit and outstanding > obj.credit_limit,
    })


@login_required
def customer_profile_edit(request, pk):
    return crud_edit(request, model=CustomerProfile, pk=pk, form_class=CustomerProfileForm,
                     template="accounting/customer_profile_form.html", success_url="accounting:customer_profile_list")


@login_required
@require_POST
def customer_profile_delete(request, pk):
    return crud_delete(request, model=CustomerProfile, pk=pk, success_url="accounting:customer_profile_list")


# ==================================================================== 2.4 AR — Invoices
@login_required
def invoice_list(request):
    return crud_list(
        request, Invoice.objects.filter(tenant=request.tenant).select_related("party", "currency"),
        "accounting/invoice_list.html",
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
    return render(request, "accounting/invoice_form.html",
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
    return render(request, "accounting/invoice_detail.html", {
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


@login_required
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


# ============================================================== 2.3+2.4 — Payments
@login_required
def payment_list(request):
    return crud_list(
        request, Payment.objects.filter(tenant=request.tenant).select_related("party", "bank_account"),
        "accounting/payment_list.html",
        search_fields=["number", "party__name"],
        filters=[("direction", "direction", False), ("status", "status", False),
                 ("payment_method", "payment_method", False)],
        extra_context={"direction_choices": Payment.DIRECTION_CHOICES,
                       "status_choices": Payment.STATUS_CHOICES,
                       "method_choices": Payment.METHOD_CHOICES},
    )


@login_required
def payment_create(request):
    return crud_create(request, form_class=PaymentForm, template="accounting/payment_form.html",
                       success_url="accounting:payment_list")


@login_required
def payment_detail(request, pk):
    obj = get_object_or_404(
        Payment.objects.select_related("party", "bank_account", "currency", "journal_entry"),
        pk=pk, tenant=request.tenant,
    )
    return render(request, "accounting/payment_detail.html", {
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
                     template="accounting/payment_form.html", success_url="accounting:payment_list")


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
    write_audit_log(request.user, payment, "update",
                    {"action": "void", "reversal": reversal.number if reversal else None})
    messages.success(request, f"Payment {payment.number} voided{' — GL reversal posted' if reversal else ''}.")
    return redirect("accounting:payment_detail", pk=pk)


# ---------------------------------------------------- Payment allocations (cash application)
@login_required
def allocation_list(request):
    return crud_list(
        request, PaymentAllocation.objects.filter(payment__tenant=request.tenant)
        .select_related("payment", "invoice", "bill"),
        "accounting/allocation_list.html",
        search_fields=["payment__number", "invoice__number", "bill__number"],
        filters=[("payment", "payment_id", True)],
        extra_context={"payments": Payment.objects.filter(tenant=request.tenant)},
    )


@login_required
def allocation_create(request):
    if _need_tenant(request):
        return redirect("accounting:allocation_list")
    if request.method == "POST":
        form = PaymentAllocationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Allocation created.")
            return redirect("accounting:allocation_list")
    else:
        form = PaymentAllocationForm(tenant=request.tenant)
    return render(request, "accounting/allocation_form.html", {"form": form, "is_edit": False})


@login_required
def allocation_detail(request, pk):
    obj = get_object_or_404(
        PaymentAllocation.objects.select_related("payment", "invoice", "bill"),
        pk=pk, payment__tenant=request.tenant,
    )
    return render(request, "accounting/allocation_detail.html", {"obj": obj})


@login_required
def allocation_edit(request, pk):
    obj = get_object_or_404(PaymentAllocation, pk=pk, payment__tenant=request.tenant)
    if request.method == "POST":
        form = PaymentAllocationForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, obj, "update")
            messages.success(request, "Allocation updated.")
            return redirect("accounting:allocation_list")
    else:
        form = PaymentAllocationForm(instance=obj, tenant=request.tenant)
    return render(request, "accounting/allocation_form.html", {"form": form, "obj": obj, "is_edit": True})


@login_required
@require_POST
def allocation_delete(request, pk):
    obj = get_object_or_404(PaymentAllocation, pk=pk, payment__tenant=request.tenant)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Deleted successfully.")
    return redirect("accounting:allocation_list")


# ============================================================== 2.5 Cash — Bank accounts
@login_required
def bank_account_list(request):
    return crud_list(
        request, BankAccount.objects.filter(tenant=request.tenant).select_related("currency", "gl_account"),
        "accounting/bank_account_list.html",
        search_fields=["name", "bank_name"],
        filters=[("currency", "currency_id", True), ("is_active", "is_active", False)],
        extra_context={"currencies": Currency.objects.filter(is_active=True)},
    )


@login_required
def bank_account_create(request):
    return crud_create(request, form_class=BankAccountForm, template="accounting/bank_account_form.html",
                       success_url="accounting:bank_account_list")


@login_required
def bank_account_detail(request, pk):
    obj = get_object_or_404(BankAccount.objects.select_related("currency", "gl_account"),
                            pk=pk, tenant=request.tenant)
    return render(request, "accounting/bank_account_detail.html", {
        "obj": obj,
        "transactions": obj.transactions.all()[:10],
        "current_balance": obj.current_balance(),
    })


@login_required
def bank_account_edit(request, pk):
    return crud_edit(request, model=BankAccount, pk=pk, form_class=BankAccountForm,
                     template="accounting/bank_account_form.html", success_url="accounting:bank_account_list")


@login_required
@require_POST
def bank_account_delete(request, pk):
    return crud_delete(request, model=BankAccount, pk=pk, success_url="accounting:bank_account_list")


# ============================================================ 2.5 Cash — Bank transactions
@login_required
def bank_transaction_list(request):
    return crud_list(
        request, BankTransaction.objects.filter(tenant=request.tenant).select_related("bank_account"),
        "accounting/bank_transaction_list.html",
        search_fields=["description", "external_ref"],
        filters=[("bank_account", "bank_account_id", True), ("direction", "direction", False),
                 ("status", "status", False)],
        extra_context={"bank_accounts": BankAccount.objects.filter(tenant=request.tenant),
                       "direction_choices": BankTransaction.DIRECTION_CHOICES,
                       "status_choices": BankTransaction.STATUS_CHOICES},
    )


@login_required
def bank_transaction_create(request):
    return crud_create(request, form_class=BankTransactionForm, template="accounting/bank_transaction_form.html",
                       success_url="accounting:bank_transaction_list")


@login_required
def bank_transaction_detail(request, pk):
    obj = get_object_or_404(BankTransaction.objects.select_related("bank_account"), pk=pk, tenant=request.tenant)
    return render(request, "accounting/bank_transaction_detail.html", {
        "obj": obj,
        "match": obj.matches.select_related("payment", "journal_line", "matched_by").first(),
    })


@login_required
def bank_transaction_edit(request, pk):
    return crud_edit(request, model=BankTransaction, pk=pk, form_class=BankTransactionForm,
                     template="accounting/bank_transaction_form.html", success_url="accounting:bank_transaction_list")


@login_required
@require_POST
def bank_transaction_delete(request, pk):
    return crud_delete(request, model=BankTransaction, pk=pk, success_url="accounting:bank_transaction_list")


@login_required
def bank_transaction_import_csv(request):
    """Import bank-statement rows from a CSV (columns: date, description, amount, direction).
    Idempotent on ``external_ref`` when supplied. POST-only mutation; GET shows the upload form."""
    if request.method == "POST":
        if _need_tenant(request):
            return redirect("accounting:bank_transaction_list")
        form = CsvImportForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            bank_account = form.cleaned_data["bank_account"]
            upload = form.cleaned_data["csv_file"]
            created = skipped = 0
            try:
                text = upload.read().decode("utf-8-sig", errors="replace")
            except Exception:
                messages.error(request, "Could not read the uploaded file.")
                return redirect("accounting:bank_transaction_import_csv")
            reader = csv.DictReader(io.StringIO(text))
            # Dedupe against existing external_refs in ONE query (not a per-row .exists()), build
            # the rows in memory, then a single atomic bulk_create (perf-review I-7).
            existing_refs = set(
                BankTransaction.objects.filter(tenant=request.tenant, bank_account=bank_account)
                .exclude(external_ref="").values_list("external_ref", flat=True)
            )
            to_create, seen_refs = [], set()
            for row in reader:
                row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
                raw_date = row.get("date", "")
                desc = row.get("description", "")
                try:
                    amount = Decimal(row.get("amount", "0") or "0")
                except (InvalidOperation, TypeError):
                    skipped += 1
                    continue
                direction = row.get("direction", "").lower()
                if direction not in ("credit", "debit"):
                    direction = "credit" if amount >= 0 else "debit"
                ext = (row.get("external_ref", "") or row.get("reference", ""))[:255]
                if ext and (ext in existing_refs or ext in seen_refs):
                    skipped += 1
                    continue
                parsed_date = None
                for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
                    try:
                        parsed_date = timezone.datetime.strptime(raw_date, fmt).date()
                        break
                    except (ValueError, TypeError):
                        continue
                if parsed_date is None:
                    skipped += 1
                    continue
                if ext:
                    seen_refs.add(ext)
                to_create.append(BankTransaction(
                    tenant=request.tenant, bank_account=bank_account, transaction_date=parsed_date,
                    description=desc[:512] or "(imported)", amount=abs(amount), direction=direction,
                    source="csv_import", external_ref=ext,
                ))
            with transaction.atomic():
                BankTransaction.objects.bulk_create(to_create)
            messages.success(request, f"Imported {len(to_create)} transaction(s); skipped {skipped}.")
            return redirect("accounting:bank_transaction_list")
    else:
        form = CsvImportForm(tenant=request.tenant)
    return render(request, "accounting/bank_transaction_import.html", {"form": form})


# ============================================================== 2.5 Cash — Reconciliation
@login_required
def reconciliation_list(request):
    return crud_list(
        request, ReconciliationMatch.objects.filter(tenant=request.tenant)
        .select_related("bank_transaction", "payment", "matched_by"),
        "accounting/reconciliation_list.html",
        search_fields=["bank_transaction__description"],
        filters=[("is_confirmed", "is_confirmed", False)],
    )


@login_required
def reconciliation_create(request):
    return crud_create(request, form_class=ReconciliationMatchForm, template="accounting/reconciliation_form.html",
                       success_url="accounting:reconciliation_list")


@login_required
def reconciliation_detail(request, pk):
    obj = get_object_or_404(
        ReconciliationMatch.objects.select_related(
            "bank_transaction", "payment", "journal_line", "journal_line__entry", "matched_by"),
        pk=pk, tenant=request.tenant,
    )
    return render(request, "accounting/reconciliation_detail.html", {"obj": obj})


@login_required
def reconciliation_edit(request, pk):
    return crud_edit(request, model=ReconciliationMatch, pk=pk, form_class=ReconciliationMatchForm,
                     template="accounting/reconciliation_form.html", success_url="accounting:reconciliation_list")


@login_required
@require_POST
def reconciliation_delete(request, pk):
    return crud_delete(request, model=ReconciliationMatch, pk=pk, success_url="accounting:reconciliation_list")


@tenant_admin_required
@require_POST
def reconciliation_confirm(request, pk):
    match = get_object_or_404(ReconciliationMatch, pk=pk, tenant=request.tenant)
    match.is_confirmed = not match.is_confirmed
    if match.matched_by_id is None:
        match.matched_by = request.user
    match.save(update_fields=["is_confirmed", "matched_by", "updated_at"])
    txn = match.bank_transaction
    txn.status = "reconciled" if match.is_confirmed else "matched"
    txn.save(update_fields=["status"])
    write_audit_log(request.user, match, "update", {"action": "reconcile", "confirmed": match.is_confirmed})
    messages.success(request, "Reconciliation updated.")
    return redirect("accounting:reconciliation_detail", pk=pk)
