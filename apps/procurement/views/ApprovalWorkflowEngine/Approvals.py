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
"""Procurement 6.3 Approval Workflow Engine — the queue, history and decisions.

The requisition DOCUMENT stays ``scm.PurchaseRequisition`` (L36); what this module
adds is the multi-tier chain around it: the queue resolves each pending chain's rule
live and shows its progress; a decision appends one ``RequisitionApproval`` row
inside an atomic block holding the spine row lock (the inventory 5.3 posture), and
the FINAL tier — or a rejection at any tier — performs the spine's own transition,
mirroring scm's field-for-field (status/approved_by/approved_at/decision_note).

Gating: nobody signs their OWN requisition (separation of duties, enforced inside
the lock); intermediate tiers of an elevated chain may be signed by any workspace
member; the FINAL tier — the one that flips the spine — always demands a tenant
admin, honouring scm's own approve-view contract on the write that matters.
A DOA grant covering the signer is stamped onto the row.
"""
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone

from apps.core.crud import as_db_int, paginate
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
        tenant=request.tenant, is_active=True).select_related("org_unit"))
    qs = (PurchaseRequisition.objects.filter(tenant=request.tenant,
                                             status="pending_approval")
          .select_related("requester", "org_unit").order_by("created_at"))
    pending_total = qs.count()
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(title__icontains=q)
                       | Q(requester__username__icontains=q))
    org_raw = request.GET.get("org", "").strip()
    org_number = as_db_int(org_raw)
    if org_number is not None:
        qs = qs.filter(org_unit_id=org_number)

    page = paginate(request, list(qs[:PENDING_EVALUATION_CAP]))
    page_pks = [row.pk for row in page.object_list]
    signatures = _signature_map(page_pks, request.tenant)
    lines_by_req = _lines_map(page_pks)
    rows = [_queue_row(req, signatures.get(req.pk, []), rules,
                       lines_by_req.get(req.pk),
                       user=request.user, admin=_is_admin(request.user))
            for req in page.object_list]
    stats = {
        "pending": pending_total,
        "shown": len(rows),
        "covered": sum(1 for r in rows if r["rule"] is not None),
        "multi_tier": sum(1 for r in rows if r["tier_count"] > 1),
    }
    return render(request, "procurement/approvalworkflow/queue.html", {
        "page_obj": page,
        "rows": rows,
        "stats": stats,
        "q": q,
        "truncated": pending_total > len(rows),
        "is_admin": _is_admin(request.user),
    })


def _lines_map(requisition_pks):
    """``{requisition_pk: [line rows]}`` for one page — ONE query, so the
    commodity dimension of rule matching never costs a query per candidate rule."""
    from apps.scm.models import PurchaseRequisitionLine

    grouped = {}
    for line in PurchaseRequisitionLine.objects.filter(
            requisition_id__in=requisition_pks):
        grouped.setdefault(line.requisition_id, []).append(line)
    return grouped


def _signature_map(requisition_pks, tenant):
    """``{requisition_pk: [approval rows]}`` for one page — ONE query."""
    grouped = {}
    for row in (RequisitionApproval.objects.filter(tenant=tenant,
                                                   requisition_id__in=requisition_pks)
                .select_related("approver", "via_delegation")
                .order_by("requisition_id", "tier")):
        grouped.setdefault(row.requisition_id, []).append(row)
    return grouped


def _queue_row(req, signatures, rules, lines=None, *, user=None, admin=False):
    """One computed queue row: resolved rule, progress, who may sign next."""
    rule, reason = resolve_routing(req, rules=rules,
                                   lines_by_req={req.pk: lines} if lines is not None else None)
    tier_count = rule.required_tiers if rule is not None else 1
    done = sum(1 for s in signatures if s.decision == "approved")
    rejected = any(s.decision == "rejected" for s in signatures)
    next_tier = done + 1
    is_final = next_tier >= tier_count
    elevated = req.needs_elevated_approval()
    # The three-part gate the decide verb enforces under lock, mirrored for display:
    # never your own requisition; elevated chains need an admin; and the FINAL
    # signature — the one that flips the spine — always needs an admin.
    own = user is not None and req.requester_id == user.id
    may_decide = (not own and admin) or (
        not own and not elevated and not is_final)
    if own:
        gate = "Your request — someone else signs"
    elif admin:
        gate = "You can sign"
    elif is_final:
        gate = "Final signature — admin"
    elif elevated:
        gate = "Elevated — admin"
    else:
        gate = "Open to you"
    return {
        "req": req,
        "rule": rule,
        "reason": reason,
        "tier_count": tier_count,
        "done": done,
        "next_tier": next_tier,
        "is_final": is_final,
        "elevated": elevated,
        "signatures": signatures,
        "rejected": rejected,
        "may_decide": may_decide,
        "gate": gate,
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
        tenant=request.tenant, is_active=True).select_related("org_unit"))
    signatures = _signature_map([r.pk for r in pending], request.tenant)
    lines_by_req = _lines_map([r.pk for r in pending])
    admin = _is_admin(request.user)
    # Grants where THIS user is the delegate — exactly the queues they hold
    # borrowed authority over, and what a signature they make will be stamped with.
    covering = (ApprovalDelegation.objects.filter(
                    tenant=request.tenant, delegate=request.user, is_active=True)
                .select_related("delegator", "scope_org_unit"))
    rows = []
    for req in pending:
        row = _queue_row(req, signatures.get(req.pk, []), rules,
                         lines_by_req.get(req.pk),
                         user=request.user, admin=admin)
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

    # Separation of duties: the requester can never sign their own chain — every
    # gate below runs INSIDE the spine row lock so nothing races past it.
    if requisition.requester_id == request.user.id:
        raise PermissionDenied("You cannot approve your own requisition.")

    rules = list(ApprovalRoutingRule.objects.filter(
        tenant=request.tenant, is_active=True).select_related("org_unit"))
    rule, reason = resolve_routing(requisition, rules=rules)
    tier_count = rule.required_tiers if rule is not None else 1
    done = sum(1 for s in requisition.workflow_approvals.filter(decision="approved"))
    tier = done + 1
    is_final_tier = tier >= tier_count

    elevated = requisition.needs_elevated_approval()
    if elevated and not _is_admin(request.user):
        # The spine puts the same gate on its own approve view — mirrored, not new.
        raise PermissionDenied("Elevated approvals require a tenant administrator.")
    if is_final_tier and not _is_admin(request.user):
        # The final tier performs the SPINE's own transition, so it carries scm's
        # own contract: a tenant admin signs the write that approves real spend.
        raise PermissionDenied(
            "The final signature must come from a tenant administrator.")

    form = ApprovalDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "; ".join(form.errors.get("comment", ["Invalid comment."])))
        return redirect("procurement:approval_queue")

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
