"""Procurement 6.3 Approval Workflow Engine — Escalation Management views.

A computed board over pending chains (no per-row writes) plus ONE honest
"automation" verb: there is no scheduler in this codebase, so Run fires the engine
on demand — idempotent by its open-alert probe, audited as a whole.
"""
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.core.crud import paginate
from apps.procurement.models import (
    EscalationPolicy,
    escalation_candidates,
    run_escalations,
)
from apps.procurement.views._common import *  # noqa: F401,F403


def _is_admin(request):
    return bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))


@login_required
def escalation_queue(request):
    policy = EscalationPolicy.for_tenant(request.tenant)
    rows = escalation_candidates(request.tenant, policy)
    stats = {
        "pending": len(rows),
        "idle": sum(1 for r in rows if r["is_idle"]),
        "escalated": sum(1 for r in rows if r["escalated"]),
    }
    lens = request.GET.get("lens", "").strip()
    if lens == "idle":
        rows = [r for r in rows if r["is_idle"]]
    elif lens == "raised":
        rows = [r for r in rows if r["escalated"]]
    else:
        lens = ""
    page = paginate(request, rows)
    return render(request, "procurement/approvalworkflow/escalations.html", {
        "page_obj": page,
        "rows": page.object_list,
        "policy": policy,
        "stats": stats,
        "lens": lens,
        "is_admin": _is_admin(request),
    })


@login_required
@require_POST
@transaction.atomic
def escalation_run(request):
    if not _is_admin(request):
        raise PermissionDenied("Running escalations requires a tenant administrator.")
    # The policy row lock is the per-tenant mutex: two concurrent Runs serialize,
    # so the second sees the first's alerts and raises nothing twice.
    policy = EscalationPolicy.objects.select_for_update().get(
        tenant=request.tenant)
    if not policy.is_active:
        messages.warning(request, "The escalation policy is inactive — nothing was raised.")
        return redirect("procurement:escalation_queue")
    summary = run_escalations(request.tenant, request.user, policy)
    messages.success(
        request,
        f"Escalation run: {summary['checked']} chain(s) evaluated, "
        f"{summary['raised']} alert(s) raised, "
        f"{summary['skipped_open']} already escalated.")
    return redirect("procurement:escalation_queue")
