"""SCM 4.6 Transportation Management System — FreightInvoice views (audit → approve → hand off)."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant, _tms_carrier_qs
from apps.scm.models import FreightInvoice
from apps.scm.forms import FreightInvoiceForm, FreightInvoiceLineFormSet

ZERO = Decimal("0")


@login_required
def freightinvoice_list(request):
    # No `bill` join: the list template renders only carrier.name + currency.code, not the bill.
    qs = (FreightInvoice.objects.filter(tenant=request.tenant)
          .select_related("carrier", "carrier__party", "currency"))
    return crud_list(
        request, qs, "scm/transportation/freightinvoice/list.html",
        search_fields=["number", "carrier_invoice_number", "carrier__party__name"],
        filters=[("match_status", "match_status", False),
                 ("approval_status", "approval_status", False),
                 ("carrier", "carrier_id", True)],
        extra_context={
            "match_status_choices": FreightInvoice.MATCH_STATUS_CHOICES,
            "approval_status_choices": FreightInvoice.APPROVAL_STATUS_CHOICES,
            "carriers": _tms_carrier_qs(request.tenant),
        },
    )


@login_required
def freightinvoice_create(request):
    return _freightinvoice_form(request, instance=None)


@login_required
def freightinvoice_edit(request, pk):
    obj = get_object_or_404(FreightInvoice, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "This invoice has been approved or handed off and can no longer be edited.")
        return redirect("scm:freightinvoice_detail", pk=pk)
    return _freightinvoice_form(request, instance=obj)


def _freightinvoice_form(request, instance):
    """Header + charge-line formset in ONE transaction, then amounts recomputed + audit re-run."""
    if instance is None and _need_tenant(request):
        return redirect("scm:freightinvoice_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = FreightInvoiceForm(request.POST, instance=instance, tenant=request.tenant)
        formset = FreightInvoiceLineFormSet(request.POST, instance=instance,
                                            form_kwargs={"tenant": request.tenant})
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                inv = form.save(commit=False)
                inv.tenant = request.tenant
                inv.save()
                formset.instance = inv
                formset.save()
                # Amounts and the match verdict are always derived from the CURRENT lines.
                inv.run_audit()
            write_audit_log(request.user, inv, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"Freight invoice {inv.number} saved ({inv.get_match_status_display()}).")
            return redirect("scm:freightinvoice_detail", pk=inv.pk)
    else:
        form = FreightInvoiceForm(instance=instance, tenant=request.tenant)
        formset = FreightInvoiceLineFormSet(instance=instance, form_kwargs={"tenant": request.tenant})
    return render(request, "scm/transportation/freightinvoice/form.html",
                  {"form": form, "formset": formset, "is_edit": is_edit, "obj": instance})


@login_required
def freightinvoice_detail(request, pk):
    obj = get_object_or_404(
        FreightInvoice.objects.select_related("carrier__party", "load", "shipment", "currency", "bill"),
        pk=pk, tenant=request.tenant)
    lines = list(obj.lines.all())
    return render(request, "scm/transportation/freightinvoice/detail.html", {
        "obj": obj,
        "lines": lines,
    })


@login_required
@require_POST
def freightinvoice_delete(request, pk):
    obj = get_object_or_404(FreightInvoice, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "This invoice has been approved or handed off and can't be deleted.")
        return redirect("scm:freightinvoice_detail", pk=pk)
    return crud_delete(request, model=FreightInvoice, pk=pk, success_url="scm:freightinvoice_list")


@login_required
@require_POST
def freightinvoice_run_audit(request, pk):
    """Re-run the billed-vs-contract match against the tolerance."""
    # select_related so write_audit_log -> str(obj) -> carrier.name -> party.name doesn't chain-fetch.
    obj = get_object_or_404(FreightInvoice.objects.select_related("carrier__party"),
                            pk=pk, tenant=request.tenant)
    status = obj.run_audit()
    write_audit_log(request.user, obj, "update", {"action": "run_audit", "match_status": status})
    messages.success(request, f"Audit run — {obj.get_match_status_display()} "
                              f"(variance {obj.variance_amount}).")
    return redirect("scm:freightinvoice_detail", pk=pk)


@login_required
@require_POST
def freightinvoice_dispute(request, pk):
    """Flag a variant invoice as disputed with a written reason (holds it out of approval)."""
    obj = get_object_or_404(FreightInvoice.objects.select_related("carrier__party"),
                            pk=pk, tenant=request.tenant)
    if obj.approval_status == "approved":
        messages.error(request, "An approved invoice can't be disputed — reject the linked bill in accounting.")
        return redirect("scm:freightinvoice_detail", pk=pk)
    reason = (request.POST.get("dispute_reason") or "").strip()
    if not reason:
        messages.error(request, "Give a reason for the dispute.")
        return redirect("scm:freightinvoice_detail", pk=pk)
    obj.match_status = "disputed"
    obj.dispute_reason = reason
    obj.save(update_fields=["match_status", "dispute_reason", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "dispute", "reason": reason})
    messages.warning(request, f"Freight invoice {obj.number} marked disputed.")
    return redirect("scm:freightinvoice_detail", pk=pk)


@tenant_admin_required
@require_POST
def freightinvoice_approve(request, pk):
    """Approve the invoice for payment. Tenant-admin gated; a disputed invoice must be resolved first."""
    obj = get_object_or_404(FreightInvoice.objects.select_related("carrier__party"),
                            pk=pk, tenant=request.tenant)
    if obj.match_status == "disputed":
        messages.error(request, "Resolve the dispute (re-run the audit) before approving.")
        return redirect("scm:freightinvoice_detail", pk=pk)
    # Only a PENDING invoice can be approved — never re-approve an already-approved one, and never
    # push a rejected one straight to approved via a crafted POST without going back through edit/audit
    # (mirrors requisition_approve's status guard; the button is pending-only in the template too).
    if obj.approval_status != "pending":
        messages.info(request, f"This invoice is already {obj.get_approval_status_display().lower()}.")
        return redirect("scm:freightinvoice_detail", pk=pk)
    obj.approval_status = "approved"
    obj.approved_by = request.user
    obj.approved_at = timezone.now()
    obj.save(update_fields=["approval_status", "approved_by", "approved_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "approve"})
    messages.success(request, f"Freight invoice {obj.number} approved.")
    return redirect("scm:freightinvoice_detail", pk=pk)


@tenant_admin_required
@require_POST
def freightinvoice_reject(request, pk):
    obj = get_object_or_404(FreightInvoice.objects.select_related("carrier__party"),
                            pk=pk, tenant=request.tenant)
    # Only a PENDING invoice can be rejected — a crafted POST must not overturn an already-approved
    # invoice (which would leave approved_by/approved_at pointing at the prior approver). The bill_id
    # case is a subset of "not pending" (hand-off requires approval first) but keeps a clearer message.
    if obj.bill_id is not None:
        messages.error(request, "This invoice has already been handed off to a bill and can't be rejected here.")
        return redirect("scm:freightinvoice_detail", pk=pk)
    if obj.approval_status != "pending":
        messages.info(request, f"This invoice is already {obj.get_approval_status_display().lower()}.")
        return redirect("scm:freightinvoice_detail", pk=pk)
    obj.approval_status = "rejected"
    obj.save(update_fields=["approval_status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "reject"})
    messages.success(request, f"Freight invoice {obj.number} rejected.")
    return redirect("scm:freightinvoice_detail", pk=pk)


@tenant_admin_required
@require_POST
def freightinvoice_handoff(request, pk):
    """Draft an ``accounting.Bill`` for the carrier and link it — the AP hand-off (L29).

    A DRAFT bill only: TMS never posts the journal entry. The AP team approves + pays the bill in
    accounting, which is where the GL effect is recorded. The carrier's ``party`` is the bill's
    (PROTECT, required) vendor — always present because a carrier is a spine-backed party.
    """
    obj = get_object_or_404(FreightInvoice.objects.select_related("carrier__party"),
                            pk=pk, tenant=request.tenant)
    if obj.approval_status != "approved":
        messages.error(request, "Approve the freight invoice before handing it off to a bill.")
        return redirect("scm:freightinvoice_detail", pk=pk)
    if obj.bill_id is not None:
        messages.info(request, f"Already handed off to bill {obj.bill.number}.")
        return redirect("scm:freightinvoice_detail", pk=pk)
    from apps.accounting.models import Bill, BillLine
    with transaction.atomic():
        bill = Bill(tenant=request.tenant, party=obj.carrier.party, bill_date=timezone.localdate(),
                    due_date=obj.due_date, status="draft", currency=obj.currency,
                    notes=f"Freight — {obj.number}"
                          + (f" (carrier invoice {obj.carrier_invoice_number})" if obj.carrier_invoice_number else ""))
        bill.save()
        BillLine.objects.create(
            bill=bill, description=f"Freight charges — {obj.number}",
            quantity=Decimal("1"), unit_price=obj.billed_amount)
        bill.recalc_totals()
        obj.bill = bill
        obj.save(update_fields=["bill", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "handoff", "bill": bill.number})
    messages.success(request, f"Drafted bill {bill.number} for {obj.carrier.name} — approve it in Accounts Payable.")
    return redirect("scm:freightinvoice_detail", pk=pk)
