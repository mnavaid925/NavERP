"""Inventory 5.3 Purchase Order (PO) Management — the multi-tier approval queue.

**Approval Workflows bullet.** SCM's own approve action is one tenant-admin signature; this
queue is the tiered path. For every order the spine holds at ``pending_approval``, the
matching routing rule is resolved live (value band + org unit, most-specific-wins) and the
chain's progress is replayed from the decision rows: a rejection resets the count, later
approvals rebuild it.

Clearing the FINAL tier performs the spine's own transition (status/approved_by/approved_at
— exactly what ``scm.purchaseorder_approve`` writes); a rejection returns the order to
``draft`` so the buyer can amend and resubmit. This module invents no new PO state — it
drives the nine-state lifecycle SCM already owns.
"""
from django.db import transaction
from django.utils import timezone

from apps.core.decorators import tenant_admin_required
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.models import (
    PurchaseOrderApproval,
    PurchaseOrderApprovalRule,
)
from apps.scm.models import PurchaseOrder


#: When no active rule matches an order, ONE signature is required — a fallback policy,
#: not a bypass: nothing reaches ``approved`` with zero recorded decisions.
DEFAULT_TIER_COUNT = 1


def _required_tiers(rule):
    return rule.tier_count if rule else DEFAULT_TIER_COUNT


def _pending_orders(tenant):
    if tenant is None:
        return PurchaseOrder.objects.none()
    return (PurchaseOrder.objects.filter(tenant=tenant, status="pending_approval")
            .select_related("vendor", "ship_to")
            .order_by("-id"))


@login_required
def approval_queue(request):
    """The console over pending orders + the recent-decision trail."""
    tenant = request.tenant
    pending = list(_pending_orders(tenant)[:100])  # bounded like every other table
    chain = {}
    if pending:
        rows = (PurchaseOrderApproval.objects
                .filter(tenant=tenant, purchase_order_id__in=[p.pk for p in pending])
                .select_related("decided_by", "rule")
                .order_by("decided_at", "id"))
        for row in rows:
            chain.setdefault(row.purchase_order_id, []).append(row)

    # ONE rules fetch for the whole queue; resolution is pure Python per order.
    active_rules = list(PurchaseOrderApprovalRule.objects.filter(tenant=tenant, is_active=True))
    queue = []
    for po in pending:
        decisions = chain.get(po.pk, [])
        rule = PurchaseOrderApprovalRule.resolve_from(active_rules, po.total, po.ship_to_id)
        cleared = PurchaseOrderApproval.cleared_tier_count(decisions)
        required = _required_tiers(rule)
        queue.append({
            "po": po,
            "rule": rule,
            "required": required,
            "cleared": min(cleared, required),
            "next_tier": cleared + 1,
            "done": cleared >= required,
            "decisions": decisions,
        })

    recent = (PurchaseOrderApproval.objects.filter(tenant=tenant)
              .select_related("purchase_order", "purchase_order__vendor", "decided_by", "rule")
              .order_by("-decided_at", "-id")[:12])
    return render(request, "inventory/po/approvals.html", {
        "queue": queue,
        "recent": recent,
        "default_tiers": DEFAULT_TIER_COUNT,
        # The tier verbs are tenant-admin gated server-side; the buttons hide for everyone else.
        "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
    })


def _decide(request, po_pk, tier, approving):
    """Record one tier's decision; the two URL verbs are thin wrappers around this.

    Tenant-admin gated like scm's approve: clearing tiers commits tenant money to a vendor.
    The whole read-guard-write runs under ``select_for_update`` on the ORDER row: two admins
    hitting the same next tier serialize, and the loser re-reads the chain the winner just
    extended. There is deliberately no ``(po, tier)`` uniqueness to fall back on — that
    constraint bricked every rejected-then-resubmitted chain (the replay resets progress to
    tier 1 while the previous run's row still occupied the slot) — sequential integrity here
    is the lock's job.
    """
    with transaction.atomic():
        po = get_object_or_404(
            PurchaseOrder.objects.select_for_update(), pk=po_pk, tenant=request.tenant)
        if po.status != "pending_approval":
            messages.info(request, "This order is not awaiting approval.")
            return redirect("inventory:approval_queue")

        decisions = list(PurchaseOrderApproval.objects
                         .filter(tenant=request.tenant, purchase_order=po)
                         .order_by("decided_at", "id"))
        cleared = PurchaseOrderApproval.cleared_tier_count(decisions)
        if tier != cleared + 1:
            messages.error(request, f"Tier {cleared + 1} must be decided first.")
            return redirect("inventory:approval_queue")

        rule = PurchaseOrderApprovalRule.resolve(request.tenant, po.total, po.ship_to_id)
        required = _required_tiers(rule)

        decision_row = PurchaseOrderApproval.objects.create(
            tenant=request.tenant, purchase_order=po, rule=rule, tier=tier,
            decision="approved" if approving else "rejected",
            decided_by=request.user, decided_at=timezone.now(),
            note=(request.POST.get("note") or "").strip()[:2000],
        )
        write_audit_log(request.user, decision_row, "create",
                        {"action": "tier_approve" if approving else "tier_reject",
                         "tier": tier})
        if approving:
            if tier >= required:
                # The spine's own final transition — same fields scm's approve writes.
                po.status = "approved"
                po.approved_by = request.user
                po.approved_at = timezone.now()
                po.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
                write_audit_log(request.user, po, "update", {"action": "approve"})
                messages.success(
                    request, f"Order {po.number} approved — all {required} tier(s) cleared.")
            else:
                messages.success(
                    request, f"Tier {tier} of {required} recorded for order {po.number}.")
        else:
            po.status = "draft"  # back to the buyer; scm has no rejected state for orders
            po.save(update_fields=["status", "updated_at"])
            write_audit_log(request.user, po, "update", {"action": "reject"})
            messages.success(
                request, f"Order {po.number} returned to draft — amend and resubmit it.")
    return redirect("inventory:approval_queue")


@tenant_admin_required
@require_POST
def approval_tier_approve(request, po_pk, tier):
    return _decide(request, po_pk, tier, approving=True)


@tenant_admin_required
@require_POST
def approval_tier_reject(request, po_pk, tier):
    return _decide(request, po_pk, tier, approving=False)
