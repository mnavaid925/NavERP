"""Sales 8.17 — SalesApprovalDecision views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.sales.forms.WorkflowProcessAutomation.SalesApprovalDecisions import (
    SalesApprovalDecisionActionForm,
    SalesApprovalDecisionEditForm,
    SalesApprovalDecisionForm,
)
from apps.sales.models.ContractSubscriptionManagement.CustomerContracts import CustomerContract
from apps.sales.models.OrderManagement.OrderHolds import OrderHold
from apps.sales.models.QuoteProposalCPQ.CPQQuotes import CPQQuote
from apps.sales.models.WorkflowProcessAutomation.SalesApprovalDecisions import (
    TARGET_KIND_CHOICES,
    SalesApprovalDecision,
)

SAD_TARGET_MODELS = {"quote": CPQQuote, "order_hold": OrderHold, "contract": CustomerContract}
TARGET_KIND_TO_APPROVAL_KIND = {"quote": "discount", "order_hold": "credit", "contract": "contract"}

# Pinned explicitly (not left to Meta.ordering) on every chain/tier query: an unordered
# read feeding a tier comparison is a latent idempotency bug (L61).
_CHAIN_ORDER = ("target_key", "tier", "id")


@login_required
def sales_approval_decision_list(request):
    tenant = request.tenant
    qs = SalesApprovalDecision.objects.filter(tenant=tenant).select_related(
        "approver", "quote", "order_hold", "contract"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q) | Q(record_label__icontains=q) | Q(comment__icontains=q)
        )

    # String-enum filters (L11/L44): junk GET values skip the filter, never 500.
    approval_kind = request.GET.get("approval_kind", "").strip()
    if approval_kind in {value for value, _ in SalesApprovalDecision.APPROVAL_KIND_CHOICES}:
        qs = qs.filter(approval_kind=approval_kind)

    decision = request.GET.get("decision", "").strip()
    if decision in {value for value, _ in SalesApprovalDecision.DECISION_CHOICES}:
        qs = qs.filter(decision=decision)

    target_kind = request.GET.get("target_kind", "").strip()
    if target_kind in {value for value, _ in TARGET_KIND_CHOICES}:
        qs = qs.filter(target_key__startswith=f"{target_kind}:")

    page_obj = paginate(request, qs, 15)
    context = {
        "approval_decisions": page_obj.object_list,
        "page_obj": page_obj,
        "approval_kind_choices": SalesApprovalDecision.APPROVAL_KIND_CHOICES,
        "decision_choices": SalesApprovalDecision.DECISION_CHOICES,
        "target_kind_choices": TARGET_KIND_CHOICES,
    }
    return render(request, "sales/workflowprocessautomation/salesapprovaldecision/list.html", context)


@login_required
def sales_approval_decision_detail(request, pk):
    """The chain view: pending-ness is DERIVED from the rows, never read from a status field."""
    tenant = request.tenant
    approval_decision = get_object_or_404(
        SalesApprovalDecision.objects.filter(tenant=tenant).select_related(
            "approver", "approver_role", "approval_rule", "requested_by",
            "quote", "order_hold", "contract"
        ),
        pk=pk,
    )

    chain = list(
        SalesApprovalDecision.objects.filter(
            tenant=tenant, target_key=approval_decision.target_key
        )
        .select_related("approver", "approver_role")
        .order_by(*_CHAIN_ORDER)
    )
    rejected_exists = any(row.decision == "rejected" for row in chain)
    approved_count = sum(1 for row in chain if row.decision == "approved")
    tier_count = max((row.tier_count for row in chain), default=1)
    # Pending = the ABSENCE of a row at the current tier. A rejection closes the chain
    # at any tier, and a fully-approved chain has no next tier either.
    pending_tier = (
        None if rejected_exists or approved_count >= tier_count else approved_count + 1
    )

    kind, _, pk_str = approval_decision.target_key.partition(":")
    target_pk = as_db_int(pk_str)
    target_model = SAD_TARGET_MODELS.get(kind)
    target_object = None
    if target_model is not None and target_pk is not None:
        target_object = target_model.objects.filter(tenant=tenant, pk=target_pk).first()

    action_form = None
    if pending_tier is not None:
        action_form = SalesApprovalDecisionActionForm(tenant=tenant, initial={
            "target_kind": kind,
            "target_id": target_pk,
            "tier_count": tier_count,
            "approval_kind": TARGET_KIND_TO_APPROVAL_KIND.get(kind, ""),
        })

    context = {
        "approval_decision": approval_decision,
        "chain": chain,
        "target_object": target_object,
        "pending_tier": pending_tier,
        "tier_count": tier_count,
        "action_form": action_form,
    }
    return render(request, "sales/workflowprocessautomation/salesapprovaldecision/detail.html", context)


@login_required
@tenant_admin_required
@transaction.atomic
def sales_approval_decision_create(request):
    """Manual ledger entry — back-fills a sign-off that happened outside the system."""
    tenant = request.tenant
    if request.method == "POST":
        form = SalesApprovalDecisionForm(request.POST, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.save()  # save() computes target_key from the target FKs just set
            write_audit_log(request.user, obj, "create", tenant=tenant)
            messages.success(request, f"Approval decision '{obj.number}' recorded.")
            return redirect("sales:sales_approval_decision_detail", pk=obj.pk)
    else:
        form = SalesApprovalDecisionForm(tenant=tenant)

    context = {
        "form": form,
        "approval_decision": None,
        "is_edit": False,
    }
    return render(request, "sales/workflowprocessautomation/salesapprovaldecision/form.html", context)


@login_required
@tenant_admin_required
@transaction.atomic
def sales_approval_decision_edit(request, pk):
    """Restricted edit: comment / due_at only (SalesApprovalDecisionEditForm)."""
    tenant = request.tenant
    obj = get_object_or_404(SalesApprovalDecision.objects.filter(tenant=tenant), pk=pk)
    if request.method == "POST":
        form = SalesApprovalDecisionEditForm(request.POST, instance=obj, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save()
            write_audit_log(request.user, obj, "update", tenant=tenant)
            messages.success(request, f"Approval decision '{obj.number}' updated.")
            return redirect("sales:sales_approval_decision_detail", pk=obj.pk)
    else:
        form = SalesApprovalDecisionEditForm(instance=obj, tenant=tenant)

    context = {
        "form": form,
        "approval_decision": obj,
        "is_edit": True,
    }
    return render(request, "sales/workflowprocessautomation/salesapprovaldecision/form.html", context)


@login_required
@require_POST
@tenant_admin_required
@transaction.atomic
def sales_approval_decision_delete(request, pk):
    """Mis-entry correction only — an approved chain is not meant to be deletable."""
    tenant = request.tenant
    obj = get_object_or_404(SalesApprovalDecision.objects.filter(tenant=tenant), pk=pk)
    number = obj.number
    write_audit_log(request.user, obj, "delete", tenant=tenant)
    obj.delete()
    messages.success(request, f"Approval decision '{number}' deleted.")
    return redirect("sales:sales_approval_decision_list")


def _sales_approval_decide(request, decision):
    """Append one tier sign-off — or close the chain — under the target row lock.

    ``decision`` is the STORED value (``"approved"`` / ``"rejected"``); the public view
    supplies which one. Procurement ``approval_decide`` choreography: every guard below
    runs INSIDE the caller's ``transaction.atomic()`` and after
    ``select_for_update()`` on the target spine row, so two concurrent sign-offs on one
    target cannot both read the same tier.
    """
    tenant = request.tenant
    form = SalesApprovalDecisionActionForm(request.POST, tenant=tenant)
    if not form.is_valid():
        messages.error(request, "Fix the decision form before signing.")
        return redirect("sales:sales_approval_decision_list")

    kind = form.cleaned_data["target_kind"]
    target_id = form.cleaned_data["target_id"]

    # IDOR-safe: the target must exist AND belong to this workspace, else 404.
    target = get_object_or_404(
        SAD_TARGET_MODELS[kind].objects.select_for_update(), pk=target_id, tenant=tenant
    )

    # Same string the model's save() computes for this target — the chain's identity.
    target_key = f"{kind}:{target.pk}"
    chain = SalesApprovalDecision.objects.filter(
        tenant=tenant, target_key=target_key
    ).order_by(*_CHAIN_ORDER)

    if chain.filter(decision="rejected").exists():
        messages.error(request, "This approval chain is closed — a rejection already ended it.")
        return redirect("sales:sales_approval_decision_list")

    # Quote-only guards (separation of duties, procurement pattern). OrderHold and
    # CustomerContract have no approval_status/owner of their own on this path.
    if kind == "quote":
        if target.approval_status in {"approved", "rejected"}:
            messages.error(request, f"Quote '{target.number}' already has a final approval status.")
            return redirect("sales:sales_approval_decision_list")
        if target.owner_id == request.user.pk:
            messages.error(request, "You cannot sign an approval on a quote you own.")
            return redirect("sales:sales_approval_decision_list")

    # Chain length: the optional form value, else the longest snapshot already recorded
    # for this target, else a single-tier chain. Sales has NO `required_tiers` field and
    # QuoteApprovalRule.approver_role is a CharField (a role NAME), so neither can
    # resolve a tier count (contract §10 deviation 8). `tier` is the deterministic count
    # of approved rows + 1 — never an unordered `.first()` (L61).
    tier_count = (
        form.cleaned_data.get("tier_count")
        or chain.aggregate(Max("tier_count"))["tier_count__max"]
        or 1
    )
    tier = chain.filter(decision="approved").count() + 1
    if tier > tier_count:
        messages.error(request, "Every tier in this chain is already signed.")
        return redirect("sales:sales_approval_decision_list")

    approval_kind = form.cleaned_data.get("approval_kind") or TARGET_KIND_TO_APPROVAL_KIND[kind]

    row = SalesApprovalDecision.record(
        tenant,
        quote=target if kind == "quote" else None,
        order_hold=target if kind == "order_hold" else None,
        contract=target if kind == "contract" else None,
        approval_kind=approval_kind,
        tier=tier,
        tier_count=tier_count,
        decision=decision,
        approver=request.user,
        # approver_role stays None this pass: QuoteApprovalRule.approver_role is a
        # CharField, not a Role FK, so there is nothing to resolve it from.
        approval_rule=(target.approval_rule if kind == "quote" else None),
        requested_by=request.user,
        requested_at=timezone.now(),
        record_label=(target.number or str(target))[:200],
        comment=form.cleaned_data.get("comment", ""),
    )

    # Only the quote spine flips — OrderHold / CustomerContract targets get the decision
    # row + audit and nothing else; 8.6 (hold release) and 8.15 (contract workflow) own
    # those status transitions, so SAD never becomes a second writer on them
    # (contract §10 deviation 10). A rejection closes the chain at ANY tier.
    if kind == "quote" and decision == "approved" and tier >= tier_count:
        target.approval_status = "approved"
        target.approved_by = request.user
        target.approved_at = timezone.now()
        target.save(update_fields=["approval_status", "approved_by", "approved_at", "updated_at"])
    elif kind == "quote" and decision == "rejected":
        target.approval_status = "rejected"
        target.approved_by = request.user
        target.approved_at = timezone.now()
        target.save(update_fields=["approval_status", "approved_by", "approved_at", "updated_at"])

    # Mirrored to core.AuditLog: the register holds the business shape, the audit log the
    # tamper-evident one. Short verb in `action`, descriptive verb in `changes` (utils clamp).
    write_audit_log(
        request.user,
        row,
        "create",
        changes={
            "action": "tier_approve" if decision == "approved" else "tier_reject",
            "tier": f"{tier}/{tier_count}",
            "target": target_key,
        },
        tenant=tenant,
    )

    messages.success(request, f"Tier {tier} of {tier_count} {decision}.")
    return redirect("sales:sales_approval_decision_detail", pk=row.pk)


@login_required
@require_POST
@tenant_admin_required
@transaction.atomic
def sales_approval_decision_approve(request):
    return _sales_approval_decide(request, "approved")


@login_required
@require_POST
@tenant_admin_required
@transaction.atomic
def sales_approval_decision_reject(request):
    return _sales_approval_decide(request, "rejected")
