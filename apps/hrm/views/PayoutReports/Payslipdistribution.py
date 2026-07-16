"""HRM 3.17 Payout & Reports — Payslipdistribution views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PayoutReports._helpers import _mark_sent
from apps.hrm.models import (
    PayoutPayment,
    PayrollCycle,
    PayslipDistribution,
)
from apps.hrm.views.PayoutReports._helpers import _mark_sent


# ---------------------------------------------------------- PayslipDistribution
@login_required
def payslipdistribution_list(request):
    return crud_list(
        request,
        # No payslip__cycle join — the list renders only payslip.number + employee.party.name; the cycle
        # filter is an _id lookup and the ordering join is added by the ORM independently.
        PayslipDistribution.objects.filter(tenant=request.tenant)
        .select_related("payslip__employee__party"),
        "hrm/payout/payslipdistribution/list.html",
        search_fields=["payslip__number", "payslip__employee__party__name"],
        filters=[("status", "status", False), ("delivery_channel", "delivery_channel", False),
                 ("cycle", "payslip__cycle_id", True)],
        extra_context={
            "status_choices": PayslipDistribution.STATUS_CHOICES,
            "delivery_channel_choices": PayslipDistribution.DELIVERY_CHANNEL_CHOICES,
            "cycles": PayrollCycle.objects.filter(tenant=request.tenant),
        },
    )


@login_required
def payslipdistribution_detail(request, pk):
    obj = get_object_or_404(
        PayslipDistribution.objects.select_related("payslip__employee__party", "sent_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/payout/payslipdistribution/detail.html", {"obj": obj})


@tenant_admin_required
@require_POST
def payslipdistribution_send(request, pk):
    """Mark one payslip's distribution as sent (actual PDF+SMTP deferred). Soft-warns if the payslip's
    payout isn't paid yet (Deel's payment-before-payslip ordering — a warning, not a hard block)."""
    dist = get_object_or_404(
        PayslipDistribution.objects.select_related("payslip__employee"), pk=pk, tenant=request.tenant)
    _mark_sent(dist, request.user)
    if not PayoutPayment.objects.filter(
            tenant=request.tenant, payslip=dist.payslip, status="paid").exists():
        messages.warning(request, "Payslip sent, but this employee's payout is not yet marked paid.")
    else:
        messages.success(request, "Payslip marked sent.")
    write_audit_log(request.user, dist, "update", {"action": "send"})
    return redirect("hrm:payslipdistribution_detail", pk=dist.pk)


@tenant_admin_required
@require_POST
def payslipdistribution_send_cycle(request):
    """Bulk: ensure a distribution row exists for every payslip of the POSTed cycle and mark them sent."""
    cycle_id = request.POST.get("cycle", "").strip()
    if not cycle_id.isdigit():
        messages.error(request, "Select a cycle to distribute.")
        return redirect("hrm:payslipdistribution_list")
    cycle = get_object_or_404(PayrollCycle, pk=int(cycle_id), tenant=request.tenant)
    count = 0
    with transaction.atomic():
        for ps in cycle.payslips.select_related("employee").all():
            _mark_sent(PayslipDistribution.for_payslip(ps), request.user)
            count += 1
    write_audit_log(request.user, cycle, "update", {"action": "distribute_payslips", "count": count})
    messages.success(request, f"Marked {count} payslip(s) sent for {cycle.number}.")
    return redirect("hrm:payslipdistribution_list")


@login_required
@require_POST
def payslipdistribution_mark_viewed(request, pk):
    # SECURITY NOTE (accepted, tracked): no User<->EmployeeProfile link exists yet, so this can't be
    # scoped to "the payslip's own employee". Intentionally left @login_required (NOT
    # @tenant_admin_required) — it discloses no data and only bumps a status/timestamp already readable
    # by any tenant user via payslipdistribution_detail. When a real ESS portal + user<->employee link
    # lands, replace the tenant filter with an ownership filter (dist.payslip.employee.user==request.user)
    # rather than gating by admin role. Forward-only.
    dist = get_object_or_404(PayslipDistribution, pk=pk, tenant=request.tenant)
    if dist.status in ("pending", "sent"):
        dist.status = "viewed"
    dist.viewed_at = timezone.now()
    dist.save(update_fields=["status", "viewed_at", "updated_at"])
    return redirect("hrm:payslipdistribution_detail", pk=dist.pk)


@login_required
@require_POST
def payslipdistribution_mark_downloaded(request, pk):
    dist = get_object_or_404(PayslipDistribution, pk=pk, tenant=request.tenant)
    dist.status = "downloaded"  # terminal signal — always advances
    dist.downloaded_at = timezone.now()
    dist.save(update_fields=["status", "downloaded_at", "updated_at"])
    return redirect("hrm:payslipdistribution_detail", pk=dist.pk)
