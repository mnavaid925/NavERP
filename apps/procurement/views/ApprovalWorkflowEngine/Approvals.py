"""Procurement 6.3 Approval Workflow Engine — the queue, history and decisions.

The requisition DOCUMENT stays ``scm.PurchaseRequisition`` (L36); what this module
adds is the multi-tier chain around it: the queue resolves each pending chain's rule
live and shows its progress; a decision appends one ``RequisitionApproval`` row
inside an atomic block holding the spine row lock (the inventory 5.3 posture), and
the FINAL tier — or a rejection at any tier — performs the spine's own transition,
mirroring scm's field-for-field (status/approved_by/approved_at/decision_note).

Gating mirrors the spine's own contract: standard-tier chains may be signed by any
workspace member; elevated tiers (manager/executive) demand a tenant admin, exactly
as 4.1's approve view does. A DOA grant covering the signer is stamped onto the row.
"""
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone

from apps.core.crud import paginate
from apps.procurement.forms import ApprovalDecisionForm
from apps.procurement.models import (
    ApprovalDelegation,
    ApprovalRoutingRule,
    RequisitionApproval,
    resolve_routing,
)
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.scm.models import PurchaseRequisition

#: How many pending chains the mobile surface offers at once — it is a pocket triage
#: list, not the register.
MINE_CAP = 50

#: Evaluation cap for the queue board — same posture as the escalation engine's cap:
#: oldest-first cut, because age IS the urgency ordering here.
PENDING_EVALUATION_CAP = 200


def _is_admin(user):
    return bool(user.is_superuser or getattr(user, "is_tenant_admin", False))


# -- read surfaces ---------------------------------------------------------------------------


@login_required
def approval_queue(request):
    rules = list(ApprovalRoutingRule.objects.filter(
        tenant=request.tenant, is_active=True))
    qs = (PurchaseRequisition.objects.filter(tenant=request.tenant,
                                             status="pending_approval")
          .select_related("requester", "org_unit").order_by("created_at"))
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(title__icontains=q)
                       | Q(requester__username__icontains=q))
    org_raw = request.GET.get("org", "").strip()
    if org_raw.isdecimal():
        qs = qs.filter(org_unit_id=int(org_raw))

    page = paginate(request, list(qs[:PENDING_EVALUATION_CAP]))
    signatures = _signature_map([row.pk for row in page.object_list], request.tenant)
    rows = [_queue_row(req, signatures.get(req.pk, []), rules)
            for req in page.object_list]
    stats = {
        "pending": page.paginator.count,
        "covered": sum(1 for r in rows if r["rule"] is not None),
        "multi_tier": sum(1 for r in rows if r["tier_count"] > 1),
    }
    return render(request, "procurement/approvalworkflow/queue.html", {
        "page_obj": page,
        "rows": rows,
        "stats": stats,
        "q": q,
        "is_admin": _is_admin(request.user),
    })


def _signature_map(requisition_pks, tenant):
    """``{requisition_pk: [approval rows]}`` for one page — ONE query."""
    grouped = {}
    for row in (RequisitionApproval.objects.filter(tenant=tenant,
                                                   requisition_id__in=requisition_pks)
                .select_related("approver", "via_delegation")
                .order_by("requisition_id", "tier")):
        grouped.setdefault(row.requisition_id, []).append(row)
    return grouped


def _queue_row(req, signatures, rules):
    """One computed queue row: resolved rule, progress, who may sign next."""
    rule, reason = resolve_routing(req, rules=rules)
    tier_count = rule.required_tiers if rule is not None else 1
    done = sum(1 for s in signatures if s.decision == "approved")
    rejected = any(s.decision == "rejected" for s in signatures)
    return {
        "req": req,
        "rule": rule,
        "reason": reason,
        "tier_count": tier_count,
        "done": done,
        "next_tier": done + 1,
        "is_final": (done + 1) >= tier_count,
        "elevated": req.needs_elevated_approval(),
        "signatures": signatures,
        "rejected": rejected,
    }


@login_required
def approval_history(request):
    qs = (RequisitionApproval.objects.filter(tenant=request.tenant)
          .select_related("requisition", "approver", "via_delegation")
          .order_by("-decided_at", "-id"))
    return crud_list(
        request, qs, "procurement/approvalworkflow/history.html",
        search_fields=["requisition__number", "requisition__title", "comment",
                       "approver__username"],
        filters=[("decision", "decision", False)],
        extra_context={
            "decision_choices": RequisitionApproval.DECISION_CHOICES,
            "signed_count": qs.count(),
        },
    )


@login_required
def approval_mine(request):
    """**Mobile Approval Interface** bullet: the pocket triage surface.

    Every pending chain, oldest first, with one-tap buttons where this user may
    actually sign (elevated tiers stay admin-only, per the spine's own contract).
    Delegations INTO this user are surfaced — those are exactly the queues they were
    given authority to clear.
    """
    pending = list(
        PurchaseRequisition.objects.filter(tenant=request.tenant,
                                           status="pending_approval")
        .select_related("requester", "org_unit")
        .order_by("created_at")[:MINE_CAP])
    rules = list(ApprovalRoutingRule.objects.filter(
        tenant=request.tenant, is_active=True))
    signatures = _signature_map([r.pk for r in pending], request.tenant)
    admin = _is_admin(request.user)
    # Grants where THIS user is the delegate — exactly the queues they hold
    # borrowed authority over, and what a signature they make will be stamped with.
    covering = (ApprovalDelegation.objects.filter(
                    tenant=request.tenant, delegate=request.user, is_active=True)
                .select_related("delegator", "scope_org_unit"))
    rows = []
    for req in pending:
        row = _queue_row(req, signatures.get(req.pk, []), rules)
        row["may_decide"] = admin or not row["elevated"]
        rows.append(row)
    return render(request, "procurement/approvalworkflow/mine.html", {
        "rows": rows,
        "covering": list(covering),
        "is_admin": admin,
    })


# -- decisions ---------------------------------------------------------------------------------


@login_required
@require_POST
@transaction.atomic
def approval_decide(request, pk, decision):
    """Append one signature — or close the chain — under the spine row lock.

    ``decision`` comes from the URL (approve|reject); anything else is a 404 before
    any lock is taken.
    """
    if decision not in ("approve", "reject"):
        raise Http404("Unknown decision.")
    requisition = get_object_or_404(
        PurchaseRequisition.objects.select_for_update(), pk=pk, tenant=request.tenant)
    if requisition.status != "pending_approval":
        messages.error(request,
                       f"{requisition.number} is {requisition.get_status_display().lower()} "
                       "— its approval chain is closed.")
        return redirect("procurement:approval_queue")

    elevated = requisition.needs_elevated_approval()
    if elevated and not _is_admin(request.user):
        # The spine puts the same gate on its own approve view — mirrored, not new.
        raise PermissionDenied("Elevated approvals require a tenant administrator.")

    form = ApprovalDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "; ".join(form.errors.get("comment", ["Invalid comment."])))
        return redirect("procurement:approval_queue")

    rules = list(ApprovalRoutingRule.objects.filter(
        tenant=request.tenant, is_active=True))
    rule, reason = resolve_routing(requisition, rules=rules)
    tier_count = rule.required_tiers if rule is not None else 1
    done = sum(1 for s in requisition.workflow_approvals.filter(decision="approved"))
    tier = done + 1

    delegation = ApprovalDelegation.active_for(
        request.tenant, request.user, requisition.org_unit_id)
    comment = form.cleaned_data.get("comment", "")
    approved = decision == "approve"

    RequisitionApproval.record(
        request.tenant, requisition, tier=tier, tier_count=tier_count,
        decision="approved" if approved else "rejected",
        approver=request.user, delegation=delegation, comment=comment)
    write_audit_log(request.user, requisition,
                    "tier_approve" if approved else "tier_reject",
                    {"tier": f"{tier}/{tier_count}",
                     "via_delegation": bool(delegation)})

    if not approved:
        requisition.status = "rejected"
        requisition.approved_by = request.user
        requisition.approved_at = timezone.now()
        requisition.decision_note = (comment or "Rejected in the approval workflow.")[:2000]
        requisition.save(update_fields=["status", "approved_by", "approved_at",
                                        "decision_note", "updated_at"])
        write_audit_log(request.user, requisition, "reject")
        messages.warning(request,
                         f"{requisition.number} rejected at tier {tier} of {tier_count}.")
        return redirect("procurement:approval_history")

    if tier < tier_count:
        messages.success(request,
                         f"{requisition.number} tier {tier} approved — {tier_count - tier} "
                         "more signature(s) to go.")
        return redirect("procurement:approval_queue")

    # Final tier performs the spine's OWN transition, field-for-field as scm does.
    requisition.status = "approved"
    requisition.approved_by = request.user
    requisition.approved_at = timezone.now()
    requisition.decision_note = (comment or "")[:2000]
    requisition.save(update_fields=["status", "approved_by", "approved_at",
                                    "decision_note", "updated_at"])
    write_audit_log(request.user, requisition, "approve",
                    {"tiers": f"{tier_count}/{tier_count}"})
    messages.success(request,
                     f"{requisition.number} fully approved after {tier_count} signature(s).")
    return redirect("procurement:approval_history")


@login_required
@require_POST
def approval_approve(request, pk):
    return approval_decide(request, pk, "approve")


@login_required
@require_POST
def approval_reject(request, pk):
    return approval_decide(request, pk, "reject")
