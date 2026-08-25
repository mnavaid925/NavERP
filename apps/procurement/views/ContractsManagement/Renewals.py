"""Procurement 6.8 Contract Management — Renewal & Expiration board views.

**Renewal & Expiration Alerts**: the computed board over the SCM spine's in-window
agreements (per-contract notice windows), plus the admin Run verb that raises 6.1
ProcurementAlerts idempotently — the escalation-engine posture, no scheduler.
"""
from apps.procurement.models.ContractsManagement.Renewals import (
    expiring_contracts,
    run_renewal_alerts_audited,
)
from apps.procurement.models import ProcurementAlert
from apps.procurement.views._common import *  # noqa: F401,F403


@login_required
def renewals_board(request):
    """Every agreement inside its renewal window, with the open-alert state marked."""
    rows = expiring_contracts(request.tenant)
    contracts = [row["contract"] for row in rows]
    open_links = set(ProcurementAlert.objects.filter(
        tenant=request.tenant, kind="contract",
        status__in=("open", "acknowledged"),
        link_url__in=[f"/scm/contracts/{c.pk}/" for c in contracts],
    ).values_list("link_url", flat=True)) if contracts else set()
    for row in rows:
        row["alerted"] = f"/scm/contracts/{row['contract'].pk}/" in open_links
        # The spine refreshes its own derived status on its pages; the board shows the
        # honest stored value without pretending to re-derive it here.
    auto_count = sum(1 for r in rows if r["auto_renews"])
    return render(request,
                  "procurement/contractsmanagement/contracts/renewals.html", {
                      "rows": rows,
                      "total": len(rows),
                      "auto_count": auto_count,
                  })


@login_required
@tenant_admin_required
@require_POST
def renewals_run(request):
    summary = run_renewal_alerts_audited(request.tenant, request.user)
    messages.success(
        request,
        f"Renewal scan complete: {summary['raised']} alert(s) raised, "
        f"{summary['skipped_open']} already open.")
    return redirect("procurement:renewals_board")
