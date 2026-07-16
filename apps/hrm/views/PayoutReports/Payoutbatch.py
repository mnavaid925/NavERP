"""HRM 3.17 Payout & Reports — Payoutbatch views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PayoutReports._helpers import _recompute_batch_status
from apps.hrm.models import (
    PayoutBatch,
    PayoutPayment,
    PayrollCycle,
)
from apps.hrm.forms import (
    PayoutBatchForm,
)
from apps.hrm.views.PayoutReports._helpers import _recompute_batch_status


# ------------------------------------------------------------ PayoutBatch (+ workflow)
@login_required
def payoutbatch_list(request):
    # Annotate the list summary columns so the page is ONE query, not one _totals() aggregate per row.
    # All aggregates traverse the same `payments` relation filtered to current (non-retried) rows — a
    # current payment has no `retries`, so its LEFT JOIN yields exactly one row: no Sum fan-out. The
    # aliases avoid clashing with the model's @property (which the detail page still uses).
    _current = Q(payments__retries__isnull=True)
    qs = (PayoutBatch.objects.filter(tenant=request.tenant).select_related("cycle")
          .annotate(
              list_headcount=Count("payments", filter=_current, distinct=True),
              list_paid=Count("payments", filter=_current & Q(payments__status="paid"), distinct=True),
              list_total=Sum("payments__net_amount", filter=_current)))
    return crud_list(
        request,
        qs,
        "hrm/payout/payoutbatch/list.html",
        search_fields=["number", "cycle__number"],
        filters=[("status", "status", False), ("bank_file_format", "bank_file_format", False),
                 ("cycle", "cycle_id", True)],
        extra_context={
            "status_choices": PayoutBatch.STATUS_CHOICES,
            "bank_file_format_choices": PayoutBatch.BANK_FILE_FORMAT_CHOICES,
            "cycles": PayrollCycle.objects.filter(tenant=request.tenant, status="locked"),
        },
    )


@login_required
def payoutbatch_create(request):
    return crud_create(request, form_class=PayoutBatchForm,
                       template="hrm/payout/payoutbatch/form.html", success_url="hrm:payoutbatch_list")


@login_required
def payoutbatch_detail(request, pk):
    obj = get_object_or_404(PayoutBatch.objects.select_related("cycle"), pk=pk, tenant=request.tenant)
    payments = (obj.payments.select_related("employee__party", "retry_of")
                .order_by("employee__party__name"))
    return render(request, "hrm/payout/payoutbatch/detail.html", {
        "obj": obj,
        "payments": payments,
        "reconciliations": obj.reconciliations.order_by("-statement_date"),
    })


@login_required
def payoutbatch_edit(request, pk):
    obj = get_object_or_404(PayoutBatch, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a draft payout batch can be edited.")
        return redirect("hrm:payoutbatch_detail", pk=obj.pk)
    return crud_edit(request, model=PayoutBatch, pk=pk, form_class=PayoutBatchForm,
                     template="hrm/payout/payoutbatch/form.html", success_url="hrm:payoutbatch_list")


@login_required
@require_POST
def payoutbatch_delete(request, pk):
    obj = get_object_or_404(PayoutBatch, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a draft payout batch can be deleted.")
        return redirect("hrm:payoutbatch_detail", pk=obj.pk)
    if obj.reconciliations.exists():
        messages.error(request, "This batch has a reconciliation and cannot be deleted.")
        return redirect("hrm:payoutbatch_detail", pk=obj.pk)
    return crud_delete(request, model=PayoutBatch, pk=pk, success_url="hrm:payoutbatch_list")


@tenant_admin_required
@require_POST
def payoutbatch_generate(request, pk):
    """(Re)generate one PayoutPayment per payslip of the batch's LOCKED cycle — draft-only. On-hold
    payslips are included as zero-action ``on_hold`` rows for audit completeness. Snapshots net_pay +
    the employee's MASKED bank details (never the raw account)."""
    batch = get_object_or_404(PayoutBatch.objects.select_related("cycle"), pk=pk, tenant=request.tenant)
    if not batch.cycle.is_locked:
        messages.error(request, "The payroll cycle must be locked before generating a payout batch.")
        return redirect("hrm:payoutbatch_detail", pk=batch.pk)
    if batch.status != "draft":
        messages.error(request, "Payments can only be (re)generated while the batch is a draft.")
        return redirect("hrm:payoutbatch_detail", pk=batch.pk)
    with transaction.atomic():
        batch.payments.all().delete()  # draft-only → no paid/failed rows to preserve
        count = 0
        for ps in batch.cycle.payslips.select_related("employee__party"):
            emp = ps.employee
            PayoutPayment.objects.create(
                tenant=request.tenant, batch=batch, payslip=ps, employee=emp,
                net_amount=ps.net_pay,
                bank_name_snapshot=emp.bank_name,
                bank_account_last4_snapshot=emp.masked_bank_account(),
                bank_routing_snapshot=emp.masked_bank_routing(),
                status="on_hold" if ps.on_hold else "pending")
            count += 1
        batch.generated_by = request.user
        batch.generated_at = timezone.now()
        batch.save(update_fields=["generated_by", "generated_at", "updated_at"])
    write_audit_log(request.user, batch, "update", {"action": "generate", "headcount": count})
    messages.success(request, f"Generated {count} payment(s) for {batch.number}.")
    return redirect("hrm:payoutbatch_detail", pk=batch.pk)


@tenant_admin_required
@require_POST
def payoutbatch_approve(request, pk):
    batch = get_object_or_404(PayoutBatch, pk=pk, tenant=request.tenant)
    if batch.status == "draft":
        if not batch.payments.exists():
            messages.error(request, "Generate payments before approving the batch.")
            return redirect("hrm:payoutbatch_detail", pk=batch.pk)
        batch.status = "approved"
        batch.approved_by = request.user
        batch.approved_at = timezone.now()
        batch.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        write_audit_log(request.user, batch, "update", {"action": "approve"})
        messages.success(request, f"Batch {batch.number} approved.")
    return redirect("hrm:payoutbatch_detail", pk=batch.pk)


@tenant_admin_required
@require_POST
def payoutbatch_disburse(request, pk):
    """Mark an approved batch as sent to the bank: pending payments → processing (initiated_at stamped).
    The actual bank-file export is deferred. Mark each payment paid/failed as the bank confirms."""
    batch = get_object_or_404(PayoutBatch, pk=pk, tenant=request.tenant)
    if batch.status != "approved":
        messages.error(request, "Only an approved batch can be disbursed.")
        return redirect("hrm:payoutbatch_detail", pk=batch.pk)
    now = timezone.now()
    with transaction.atomic():
        batch.payments.filter(status="pending").update(status="processing", initiated_at=now)
        batch.status = "disbursed"
        batch.disbursed_at = now
        batch.save(update_fields=["status", "disbursed_at", "updated_at"])
        _recompute_batch_status(batch)
    write_audit_log(request.user, batch, "update", {"action": "disburse"})
    messages.success(request, f"Batch {batch.number} disbursed — mark each payment paid/failed as the bank confirms.")
    return redirect("hrm:payoutbatch_detail", pk=batch.pk)
