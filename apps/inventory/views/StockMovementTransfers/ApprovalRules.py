"""Inventory 5.7 Stock Movement & Transfers — TransferApprovalRule views.

CRUD over approval-routing policy (**Transfer Approval Workflow bullet**, policy half).
Rules are matched live at queue time; editing one never rewrites decisions already
recorded — those snapshot the rule they were made under. Like 5.3's rule catalog,
the WRITES are tenant-admin gated: a rule IS the signature gate (it decides how many
sign-offs a movement needs), so policy edits carry the same privilege as the decisions
they govern. Reads stay open to every signed-in member.
"""
from apps.core.decorators import tenant_admin_required
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms import TransferApprovalRuleForm
from apps.inventory.models import APPLIES_TO_CHOICES, TransferApprovalRule


@login_required
def transferapprovalrule_list(request):
    qs = TransferApprovalRule.objects.filter(tenant=request.tenant)
    return crud_list(
        request, qs, "inventory/transfers/approvalrule/list.html",
        search_fields=["name"],
        filters=[("applies_to", "applies_to", False), ("is_active", "is_active", False)],
        extra_context={
            "applies_to_choices": APPLIES_TO_CHOICES,
            # Writes are tenant-admin gated server-side; hide the affordances to match.
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@login_required
def transferapprovalrule_detail(request, pk):
    obj = get_object_or_404(TransferApprovalRule, pk=pk, tenant=request.tenant)
    # Decisions taken under this rule, newest first — the audit of what the policy did.
    # Tenant-filtered explicitly (defense-in-depth): the writer stamps tenant today, but
    # this page must not depend on every future writer being as careful.
    decisions = (obj.transfer_decisions.filter(tenant=request.tenant)
                 .select_related("transfer", "decided_by")
                 .order_by("-decided_at", "-id")[:10])
    return render(request, "inventory/transfers/approvalrule/detail.html", {
        "obj": obj,
        "decisions": decisions,
        "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
    })


@login_required
@tenant_admin_required
def transferapprovalrule_create(request):
    return crud_create(
        request, form_class=TransferApprovalRuleForm,
        template="inventory/transfers/approvalrule/form.html",
        success_url="inventory:transferapprovalrule_list",
    )


@login_required
@tenant_admin_required
def transferapprovalrule_edit(request, pk):
    return crud_edit(
        request, model=TransferApprovalRule, pk=pk, form_class=TransferApprovalRuleForm,
        template="inventory/transfers/approvalrule/form.html",
        success_url="inventory:transferapprovalrule_list",
    )


@login_required
@tenant_admin_required
@require_POST
def transferapprovalrule_delete(request, pk):
    # Decision rows snapshot their rule (SET_NULL), so deleting policy never rewrites
    # what governed a past movement.
    return crud_delete(request, model=TransferApprovalRule, pk=pk,
                       success_url="inventory:transferapprovalrule_list")
