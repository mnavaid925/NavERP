"""Accounting 2.2 General Ledger — JournalEntries views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.views._helpers import _need_tenant, _reverse_journal_entry
from apps.accounting.models import (
    JournalEntry,
)
from apps.accounting.forms import (
    JournalEntryForm,
    JournalLineFormSet,
)


# =============================================================== 2.2 GL — Journal entries
@login_required
def journal_entry_list(request):
    return crud_list(
        request, JournalEntry.objects.filter(tenant=request.tenant),
        "accounting/ledger/journal_entry/list.html",
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
    return render(request, "accounting/ledger/journal_entry/form.html",
                  {"form": form, "formset": formset, "is_edit": False})


@login_required
def journal_entry_detail(request, pk):
    obj = get_object_or_404(
        JournalEntry.objects.select_related("fiscal_period", "created_by", "approved_by", "reversal_of"),
        pk=pk, tenant=request.tenant,
    )
    lines = obj.lines.select_related("gl_account", "party", "org_unit", "currency")
    debit_total, credit_total = obj.totals()
    return render(request, "accounting/ledger/journal_entry/detail.html", {
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
    return render(request, "accounting/ledger/journal_entry/form.html",
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
